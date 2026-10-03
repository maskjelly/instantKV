//! Bounded BM25 retrieval. Sparse postings share the records' redb transaction.
use crate::{
    Engine, Error, Result,
    error::storage,
    memory::{MemoryHit, hit, label, parse},
    model::Record,
    store::{RECORDS, composite, decode, expired},
};
use redb::{ReadableDatabase, ReadableTable, TableDefinition, WriteTransaction};
use rust_stemmers::{Algorithm, Stemmer};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap};

const POSTINGS: TableDefinition<&str, (u32, u32)> = TableDefinition::new("search_postings_v1");
const TERMS: TableDefinition<&str, u64> = TableDefinition::new("search_terms_v1");
// (document count, token count, generation). The reserved key is the index version.
const STATS: TableDefinition<&str, (u64, u64, u64)> = TableDefinition::new("search_stats_v1");
const STOP: &str = "a an the of in on at to for by with and or is are was were be been being that this these those as from it its";

#[derive(Debug, Clone, Serialize, Deserialize, schemars::JsonSchema)]
#[serde(default, deny_unknown_fields)]
pub struct SearchQuery {
    /// Natural-language or keyword query; at most 1024 bytes and 64 indexed terms.
    pub query: String,
    pub topic: Option<String>,
    pub tag: Option<String>,
    pub since_ms: Option<u64>,
    pub until_ms: Option<u64>,
    pub limit: usize,
    pub max_bytes: usize,
    /// Bound to the query, namespace and index generation; writes invalidate it.
    pub cursor: Option<String>,
}

impl Default for SearchQuery {
    fn default() -> Self {
        Self {
            query: String::new(),
            topic: None,
            tag: None,
            since_ms: None,
            until_ms: None,
            limit: 20,
            max_bytes: 16384,
            cursor: None,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, schemars::JsonSchema)]
pub struct SearchHit {
    /// BM25 relevance, not confidence or a probability. Comparable within this query.
    pub score: f64,
    #[serde(flatten)]
    pub hit: MemoryHit,
}

#[derive(Debug, Serialize, Deserialize, schemars::JsonSchema)]
pub struct SearchPage {
    pub items: Vec<SearchHit>,
    pub next_cursor: Option<String>,
    pub postings_scanned: usize,
    pub candidates_scanned: usize,
    pub scanned_bytes: usize,
    /// A work budget stopped scoring or candidate examination. No complete top-k guarantee.
    pub truncated: bool,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Cursor {
    namespace: String,
    query: String,
    topic: Option<String>,
    tag: Option<String>,
    since_ms: Option<u64>,
    until_ms: Option<u64>,
    generation: u64,
    posting_budget: usize,
    score_bits: u64,
    key: String,
}

fn frequencies(text: &str) -> BTreeMap<String, u32> {
    let stemmer = Stemmer::create(Algorithm::English);
    let mut words = BTreeMap::new();
    let lower = text.to_lowercase();
    for word in lower.split(|c: char| !c.is_alphanumeric()) {
        if word.is_empty()
            || word.chars().count() > 64
            || STOP.split_whitespace().any(|s| s == word)
        {
            continue;
        }
        *words.entry(stemmer.stem(word).into_owned()).or_default() += 1;
    }
    words
}

fn term_key(namespace: &str, word: &str) -> String {
    format!("{namespace}\0{word}")
}

pub(crate) fn initialize(txn: &WriteTransaction) -> Result<()> {
    let ready = txn
        .open_table(STATS)
        .map_err(storage)?
        .get("\0format")
        .map_err(storage)?
        .map(|v| v.value());
    if let Some((version, _, _)) = ready {
        if version != 1 {
            return Err(storage("unsupported search index format"));
        }
        return Ok(());
    }
    txn.open_table(POSTINGS).map_err(storage)?;
    txn.open_table(TERMS).map_err(storage)?;
    // One atomic first-open migration. Existing record bytes/revisions stay intact.
    let records = txn.open_table(RECORDS).map_err(storage)?;
    for row in records.iter().map_err(storage)? {
        let (encoded, bytes) = row.map_err(storage)?;
        let (namespace, key) = encoded
            .value()
            .split_once('\0')
            .ok_or_else(|| storage("invalid record key during search migration"))?;
        update(txn, namespace, key, None, Some(&decode(bytes.value())?))?;
    }
    txn.open_table(STATS)
        .map_err(storage)?
        .insert("\0format", (1, 0, 0))
        .map_err(storage)?;
    Ok(())
}

pub(crate) fn update(
    txn: &WriteTransaction,
    namespace: &str,
    key: &str,
    old: Option<&Record>,
    new: Option<&Record>,
) -> Result<()> {
    let old = old.map(|r| parse(&r.value)).transpose()?.flatten();
    let new = new.map(|r| parse(&r.value)).transpose()?.flatten();
    if old.is_none() && new.is_none() {
        return Ok(());
    }
    let old_words = old
        .as_ref()
        .map(|m| frequencies(&m.content))
        .unwrap_or_default();
    let new_words = new
        .as_ref()
        .map(|m| frequencies(&m.content))
        .unwrap_or_default();
    let old_len: u32 = old_words.values().sum();
    let new_len: u32 = new_words.values().sum();
    let mut stats = txn.open_table(STATS).map_err(storage)?;
    let (mut docs, mut tokens, generation) = stats
        .get(namespace)
        .map_err(storage)?
        .map(|v| v.value())
        .unwrap_or_default();
    docs = docs
        .checked_sub(u64::from(old.is_some()))
        .ok_or_else(|| storage("search document count underflow"))?;
    tokens = tokens
        .checked_sub(u64::from(old_len))
        .ok_or_else(|| storage("search token count underflow"))?;
    docs += u64::from(new.is_some());
    tokens += u64::from(new_len);
    stats
        .insert(
            namespace,
            (
                docs,
                tokens,
                generation
                    .checked_add(1)
                    .ok_or_else(|| storage("search generation overflow"))?,
            ),
        )
        .map_err(storage)?;
    let mut postings = txn.open_table(POSTINGS).map_err(storage)?;
    let mut terms = txn.open_table(TERMS).map_err(storage)?;
    let encoded = composite(namespace, key);
    let mut changed = old_words.clone();
    changed.extend(new_words.iter().map(|(k, v)| (k.clone(), *v)));
    for word in changed.keys() {
        let old_tf = old_words.get(word).copied();
        let new_tf = new_words.get(word).copied();
        if old_tf == new_tf && old_len == new_len {
            continue;
        }
        let term = term_key(namespace, word);
        let posting = format!("{term}\0{encoded}");
        if let Some(tf) = new_tf {
            postings
                .insert(posting.as_str(), (tf, new_len))
                .map_err(storage)?;
        } else {
            postings.remove(posting.as_str()).map_err(storage)?;
        }
        if old_tf.is_some() != new_tf.is_some() {
            let previous = terms
                .get(term.as_str())
                .map_err(storage)?
                .map_or(0, |v| v.value());
            let df = if new_tf.is_some() {
                previous.checked_add(1)
            } else {
                previous.checked_sub(1)
            }
            .ok_or_else(|| storage("search term count overflow/underflow"))?;
            if df == 0 {
                terms.remove(term.as_str()).map_err(storage)?;
            } else {
                terms.insert(term.as_str(), df).map_err(storage)?;
            }
        }
    }
    Ok(())
}

impl Engine {
    /// Ranked lexical retrieval: BM25 k1=1.2, b=0.75, English stemming, OR terms.
    pub fn search(&self, namespace: &str, mut query: SearchQuery) -> Result<SearchPage> {
        self.memory_namespace(namespace)?;
        query.topic = query.topic.as_deref().map(label).transpose()?;
        query.tag = query.tag.as_deref().map(label).transpose()?;
        query.query = query.query.trim().to_lowercase();
        let words = frequencies(&query.query);
        if query.query.is_empty()
            || query.query.len() > 1024
            || words.len() > 64
            || !(1..=100).contains(&query.limit)
            || !(1024..=self.config.memory.max_result_bytes).contains(&query.max_bytes)
            || query
                .since_ms
                .zip(query.until_ms)
                .is_some_and(|(a, b)| a > b)
        {
            return Err(Error::Invalid("ranked search: query 1..1024 bytes / 64 terms; limit 1..100; bounded max_bytes; ordered time range".into()));
        }
        let txn = self.database()?.begin_read().map_err(storage)?;
        let stats = txn.open_table(STATS).map_err(storage)?;
        let (docs, tokens, generation) = stats
            .get(namespace)
            .map_err(storage)?
            .map(|v| v.value())
            .unwrap_or_default();
        let cursor = query
            .cursor
            .as_deref()
            .map(|text| -> Result<Cursor> {
                if text.len() > 4096 {
                    return Err(Error::Invalid("ranked cursor too large".into()));
                }
                let c: Cursor = serde_json::from_str(text)
                    .map_err(|_| Error::Invalid("invalid ranked cursor".into()))?;
                if c.namespace != namespace
                    || c.query != query.query
                    || c.topic != query.topic
                    || c.tag != query.tag
                    || c.since_ms != query.since_ms
                    || c.until_ms != query.until_ms
                    || c.generation != generation
                    || c.posting_budget != self.config.memory.max_search_postings
                    || !f64::from_bits(c.score_bits).is_finite()
                    || f64::from_bits(c.score_bits) <= 0.0
                    || !c.key.starts_with(&format!("{namespace}\0"))
                    || c.key.len() > 512
                {
                    return Err(Error::Invalid(
                        "ranked cursor is stale or belongs to different filters; repeat search"
                            .into(),
                    ));
                }
                Ok(c)
            })
            .transpose()?;
        let make_cursor = |score: f64, key: &str| -> Result<String> {
            serde_json::to_string(&Cursor {
                namespace: namespace.into(),
                query: query.query.clone(),
                topic: query.topic.clone(),
                tag: query.tag.clone(),
                since_ms: query.since_ms,
                until_ms: query.until_ms,
                generation,
                posting_budget: self.config.memory.max_search_postings,
                score_bits: score.to_bits(),
                key: key.into(),
            })
            .map_err(storage)
        };
        let mut page = SearchPage {
            items: vec![],
            next_cursor: None,
            postings_scanned: 0,
            candidates_scanned: 0,
            scanned_bytes: 0,
            truncated: false,
        };
        if docs == 0 || tokens == 0 || words.is_empty() {
            return Ok(page);
        }
        let terms = txn.open_table(TERMS).map_err(storage)?;
        let postings = txn.open_table(POSTINGS).map_err(storage)?;
        let records = txn.open_table(RECORDS).map_err(storage)?;
        let mut plan = Vec::new();
        for word in words.keys() {
            let term = term_key(namespace, word);
            if let Some(df) = terms.get(term.as_str()).map_err(storage)? {
                plan.push((df.value(), term));
            }
        }
        plan.sort(); // Rare terms first if a posting budget stops scoring.
        let mut scores: HashMap<String, f64> = HashMap::new();
        let average = tokens as f64 / docs as f64;
        'scoring: for (df, term) in plan {
            let idf = (1.0 + (docs as f64 - df as f64 + 0.5) / (df as f64 + 0.5)).ln();
            let prefix = format!("{term}\0");
            let end = format!("{term}\u{1}");
            for row in postings
                .range(prefix.as_str()..end.as_str())
                .map_err(storage)?
            {
                if page.postings_scanned == self.config.memory.max_search_postings {
                    page.truncated = true;
                    break 'scoring;
                }
                let (key, value) = row.map_err(storage)?;
                let (tf, length) = value.value();
                let encoded = key
                    .value()
                    .strip_prefix(&prefix)
                    .ok_or_else(|| storage("invalid search posting"))?;
                let contribution = idf * f64::from(tf) * 2.2
                    / (f64::from(tf) + 1.2 * (0.25 + 0.75 * f64::from(length) / average));
                *scores.entry(encoded.into()).or_default() += contribution;
                page.postings_scanned += 1;
            }
        }
        let mut ranked: Vec<_> = scores.into_iter().collect();
        ranked.sort_unstable_by(|(ka, a), (kb, b)| b.total_cmp(a).then_with(|| ka.cmp(kb)));
        let now = self.clock.unix_ms();
        let mut last = None;
        let mut pending = false;
        let mut remaining = ranked
            .into_iter()
            .filter(|(key, score)| {
                cursor.as_ref().is_none_or(|c| {
                    *score < f64::from_bits(c.score_bits)
                        || (*score == f64::from_bits(c.score_bits) && key > &c.key)
                })
            })
            .peekable();
        for (encoded, score) in remaining.by_ref() {
            if page.candidates_scanned == self.config.memory.max_candidates {
                page.truncated = true;
                pending = true;
                break;
            }
            let bytes = records
                .get(encoded.as_str())
                .map_err(storage)?
                .ok_or_else(|| storage("search posting points to a missing record"))?;
            if page.scanned_bytes + bytes.value().len() > self.config.memory.max_scan_bytes {
                if page.candidates_scanned == 0 {
                    return Err(Error::Invalid(
                        "record exceeds configured search scan budget".into(),
                    ));
                }
                page.truncated = true;
                pending = true;
                break;
            }
            page.candidates_scanned += 1;
            page.scanned_bytes += bytes.value().len();
            let record = decode(bytes.value())?;
            let memory =
                parse(&record.value)?.ok_or_else(|| storage("invalid search posting target"))?;
            let matches = !expired(&record, now)
                && query
                    .topic
                    .as_ref()
                    .is_none_or(|v| memory.topic.as_ref() == Some(v))
                && query.tag.as_ref().is_none_or(|v| memory.tags.contains(v))
                && query.since_ms.is_none_or(|v| memory.occurred_at_ms >= v)
                && query.until_ms.is_none_or(|v| memory.occurred_at_ms <= v);
            if matches {
                let (_, key) = encoded
                    .split_once('\0')
                    .ok_or_else(|| storage("invalid search key"))?;
                page.items.push(SearchHit {
                    score,
                    hit: hit(key, record, memory),
                });
                page.next_cursor = Some(make_cursor(score, &encoded)?);
                if serde_json::to_vec(&page).map_err(storage)?.len() > query.max_bytes {
                    page.items.pop();
                    if page.items.is_empty() {
                        return Err(Error::Invalid(
                            "memory and cursor exceed max_bytes; increase the result budget".into(),
                        ));
                    }
                    pending = true;
                    break;
                }
            }
            last = Some((score, encoded));
            if page.items.len() == query.limit {
                break;
            }
        }
        page.next_cursor = if remaining.peek().is_some() || pending {
            last.map(|(score, key)| make_cursor(score, &key))
                .transpose()?
        } else {
            None
        };
        if serde_json::to_vec(&page).map_err(storage)?.len() > query.max_bytes {
            return Err(Error::Invalid(
                "search response exceeds max_bytes; increase the result budget".into(),
            ));
        }
        Ok(page)
    }
}
