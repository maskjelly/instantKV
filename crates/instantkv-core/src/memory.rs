//! Structured, indexed local memory. Ordinary KV records remain separate.
use crate::{
    Engine, Error, Result,
    config::{Purpose, StorageMode, ValueKind},
    error::storage,
    model::{Condition, Record},
    store::{RECORDS, composite, decode, expired},
};
use redb::{ReadableDatabase, Table, TableDefinition};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::ops::Bound;

pub(crate) const INDEX: TableDefinition<&str, &str> = TableDefinition::new("memory_index_v1");

#[derive(Debug, Clone, Default, Serialize, Deserialize, schemars::JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MemoryInput {
    /// A fact, preference, decision or observation; at most 16 KiB of UTF-8.
    pub content: String,
    /// Exact topic label, case-insensitive. At most 64 bytes after normalization.
    pub topic: Option<String>,
    /// Up to eight exact, case-insensitive labels.
    #[serde(default)]
    pub tags: Vec<String>,
    /// App-defined JSON fields; stored and returned, not searched by the MVP.
    #[serde(default)]
    pub metadata: Map<String, Value>,
    /// Event time in Unix milliseconds. Omit to use the server's write time.
    pub occurred_at_ms: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, schemars::JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Memory {
    #[serde(rename = "_instantkv_memory")]
    pub format: u32,
    pub content: String,
    pub topic: Option<String>,
    pub tags: Vec<String>,
    pub metadata: Map<String, Value>,
    pub occurred_at_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, schemars::JsonSchema)]
pub struct MemoryHit {
    pub key: String,
    pub revision: u64,
    pub written_at_ms: u64,
    pub expires_at_ms: Option<u64>,
    pub memory: Memory,
}

#[derive(Debug, Clone, Serialize, Deserialize, schemars::JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct RememberRequest {
    /// Omit to create a new UUID key; provide a stable key for retryable saves.
    pub key: Option<String>,
    pub memory: MemoryInput,
    pub ttl_seconds: Option<u64>,
    /// Omit for create-only; supply the observed revision to update a memory.
    pub if_revision: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, schemars::JsonSchema)]
#[serde(default, deny_unknown_fields)]
pub struct MemoryQuery {
    pub topic: Option<String>,
    pub tag: Option<String>,
    /// All whitespace-separated terms must occur in content, case-insensitively.
    pub query: Option<String>,
    /// Inclusive event-time range in Unix milliseconds.
    pub since_ms: Option<u64>,
    pub until_ms: Option<u64>,
    pub limit: usize,
    /// Total serialized response budget, including metadata and cursor.
    pub max_bytes: usize,
    /// Opaque continuation; reuse the same filters. Pages are not a snapshot.
    pub cursor: Option<String>,
}

impl Default for MemoryQuery {
    fn default() -> Self {
        Self {
            topic: None,
            tag: None,
            query: None,
            since_ms: None,
            until_ms: None,
            limit: 20,
            max_bytes: 16384,
            cursor: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, schemars::JsonSchema)]
pub struct MemoryPage {
    pub items: Vec<MemoryHit>,
    pub next_cursor: Option<String>,
    pub scanned: usize,
    pub scanned_bytes: usize,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Cursor {
    namespace: String,
    topic: Option<String>,
    tag: Option<String>,
    query: Option<String>,
    since_ms: Option<u64>,
    until_ms: Option<u64>,
    position: String,
}

fn label(value: &str) -> Result<String> {
    let value = value.trim().to_lowercase();
    if value.is_empty() || value.len() > 64 || value.chars().any(char::is_control) {
        return Err(Error::Invalid(
            "topic/tag must use 1..64 bytes without control characters".into(),
        ));
    }
    Ok(value)
}

impl MemoryInput {
    fn normalize(mut self, now: u64) -> Result<Memory> {
        if self.content.trim().is_empty() || self.content.len() > 16384 {
            return Err(Error::Invalid(
                "memory content must use 1..16384 bytes".into(),
            ));
        }
        if self.tags.len() > 8 {
            return Err(Error::Invalid("memory accepts at most eight tags".into()));
        }
        if serde_json::to_vec(&self.metadata).map_err(storage)?.len() > 8192 {
            return Err(Error::Invalid("memory metadata exceeds 8192 bytes".into()));
        }
        self.topic = self.topic.as_deref().map(label).transpose()?;
        self.tags = self
            .tags
            .iter()
            .map(|tag| label(tag))
            .collect::<Result<_>>()?;
        self.tags.sort();
        self.tags.dedup();
        Ok(Memory {
            format: 1,
            content: self.content,
            topic: self.topic,
            tags: self.tags,
            metadata: self.metadata,
            occurred_at_ms: self.occurred_at_ms.unwrap_or(now),
        })
    }
}

/// The marker is reserved. Raw puts cannot bypass shape or index validation.
pub(crate) fn parse(value: &[u8]) -> Result<Option<Memory>> {
    let Ok(value) = serde_json::from_slice::<Value>(value) else {
        return Ok(None);
    };
    if value.get("_instantkv_memory").is_none() {
        return Ok(None);
    }
    let memory: Memory = serde_json::from_value(value)
        .map_err(|_| Error::Invalid("invalid structured memory envelope".into()))?;
    if memory.format != 1 {
        return Err(Error::Invalid(
            "unsupported structured memory format".into(),
        ));
    }
    let normalized = MemoryInput {
        content: memory.content.clone(),
        topic: memory.topic.clone(),
        tags: memory.tags.clone(),
        metadata: memory.metadata.clone(),
        occurred_at_ms: Some(memory.occurred_at_ms),
    }
    .normalize(0)?;
    if normalized.topic != memory.topic || normalized.tags != memory.tags {
        return Err(Error::Invalid(
            "structured memory labels must be normalized and deduplicated; use remember".into(),
        ));
    }
    Ok(Some(memory))
}

fn index_keys(namespace: &str, key: &str, memory: &Memory) -> Vec<String> {
    let suffix = format!("{:020}\0{key}", memory.occurred_at_ms);
    let mut keys = vec![format!("{namespace}\0time\0{suffix}")];
    if let Some(topic) = &memory.topic {
        keys.push(format!("{namespace}\0topic\0{topic}\0{suffix}"));
    }
    for tag in &memory.tags {
        keys.push(format!("{namespace}\0tag\0{tag}\0{suffix}"));
    }
    keys
}

pub(crate) fn update_index(
    index: &mut Table<'_, &str, &str>,
    namespace: &str,
    key: &str,
    old: Option<&Record>,
    new: Option<&Record>,
) -> Result<()> {
    if let Some(old) = old
        && let Some(memory) = parse(&old.value)?
    {
        for entry in index_keys(namespace, key, &memory) {
            index.remove(entry.as_str()).map_err(storage)?;
        }
    }
    if let Some(new) = new
        && let Some(memory) = parse(&new.value)?
    {
        let encoded = composite(namespace, key);
        for entry in index_keys(namespace, key, &memory) {
            index
                .insert(entry.as_str(), encoded.as_str())
                .map_err(storage)?;
        }
    }
    Ok(())
}

fn hit(key: &str, record: Record, memory: Memory) -> MemoryHit {
    MemoryHit {
        key: key.into(),
        revision: record.revision,
        written_at_ms: record.written_at_ms,
        expires_at_ms: record.expires_at_ms,
        memory,
    }
}

impl Engine {
    fn memory_namespace(&self, namespace: &str) -> Result<()> {
        let ns = self.namespace(namespace)?;
        if ns.purpose != Purpose::Records
            || ns.mode != StorageMode::Durable
            || !matches!(ns.admission.value_kind, ValueKind::Json)
        {
            return Err(Error::Invalid(
                "structured memory requires a durable JSON records namespace".into(),
            ));
        }
        Ok(())
    }

    pub fn remember(
        &self,
        namespace: &str,
        key: &str,
        input: MemoryInput,
        ttl_seconds: Option<u64>,
        condition: Condition,
    ) -> Result<MemoryHit> {
        self.memory_namespace(namespace)?;
        let memory = input.normalize(self.clock.unix_ms())?;
        let value = serde_json::to_vec(&memory).map_err(storage)?;
        let record = self.put(namespace, key, value, ttl_seconds, condition)?;
        Ok(hit(key, record, memory))
    }

    /// Exact managed-memory lookup. Raw KV values are available through get().
    pub fn memory_get(&self, namespace: &str, key: &str) -> Result<MemoryHit> {
        self.memory_namespace(namespace)?;
        let record = self.get(namespace, key)?;
        let memory = parse(&record.value)?.ok_or(Error::NotFound)?;
        Ok(hit(key, record, memory))
    }

    /// Browse or recall newest event time first, then descending key for ties.
    pub fn recall(&self, namespace: &str, mut query: MemoryQuery) -> Result<MemoryPage> {
        self.memory_namespace(namespace)?;
        query.topic = query.topic.as_deref().map(label).transpose()?;
        query.tag = query.tag.as_deref().map(label).transpose()?;
        query.query = query
            .query
            .as_deref()
            .map(|text| text.trim().to_lowercase());
        if query.query.as_ref().is_some_and(|text| {
            text.is_empty() || text.len() > 256 || text.split_whitespace().count() > 8
        }) || !(1..=100).contains(&query.limit)
            || !(1024..=self.config.memory.max_result_bytes).contains(&query.max_bytes)
            || query
                .since_ms
                .zip(query.until_ms)
                .is_some_and(|(a, b)| a > b)
        {
            return Err(Error::Invalid("invalid query: limit 1..100, bounded max_bytes, ordered time range, query 1..256 bytes / eight terms".into()));
        }
        let prefix = if let Some(topic) = &query.topic {
            format!("{namespace}\0topic\0{topic}\0")
        } else if let Some(tag) = &query.tag {
            format!("{namespace}\0tag\0{tag}\0")
        } else {
            format!("{namespace}\0time\0")
        };
        let start = format!("{prefix}{:020}\0", query.since_ms.unwrap_or(0));
        // The next separator sorts after every key at the inclusive end time.
        let end = format!("{prefix}{:020}\u{1}", query.until_ms.unwrap_or(u64::MAX));
        let position = query
            .cursor
            .as_deref()
            .map(|text| {
                if text.len() > 4096 {
                    return Err(Error::Invalid("cursor too large".into()));
                }
                let cursor: Cursor = serde_json::from_str(text)
                    .map_err(|_| Error::Invalid("invalid memory cursor".into()))?;
                if cursor.namespace != namespace
                    || cursor.topic != query.topic
                    || cursor.tag != query.tag
                    || cursor.query != query.query
                    || cursor.since_ms != query.since_ms
                    || cursor.until_ms != query.until_ms
                    || !cursor.position.starts_with(&prefix)
                    || cursor.position < start
                    || cursor.position >= end
                {
                    return Err(Error::Invalid(
                        "cursor does not belong to these memory filters".into(),
                    ));
                }
                Ok(cursor.position)
            })
            .transpose()?;
        let make_cursor = |position: &str| -> Result<String> {
            serde_json::to_string(&Cursor {
                namespace: namespace.into(),
                topic: query.topic.clone(),
                tag: query.tag.clone(),
                query: query.query.clone(),
                since_ms: query.since_ms,
                until_ms: query.until_ms,
                position: position.into(),
            })
            .map_err(storage)
        };
        let txn = self.database()?.begin_read().map_err(storage)?;
        let records = txn.open_table(RECORDS).map_err(storage)?;
        let index = txn.open_table(INDEX).map_err(storage)?;
        let upper = position
            .as_deref()
            .map_or(Bound::Excluded(end.as_str()), Bound::Excluded);
        let mut candidates = index
            .range::<&str>((Bound::Included(start.as_str()), upper))
            .map_err(storage)?
            .rev()
            .peekable();
        let mut page = MemoryPage {
            items: vec![],
            next_cursor: None,
            scanned: 0,
            scanned_bytes: 0,
        };
        let mut last = position;
        let now = self.clock.unix_ms();
        while let Some(entry) = candidates.next() {
            let (index_key, encoded) = entry.map_err(storage)?;
            if page.scanned >= self.config.memory.max_candidates {
                break;
            }
            let bytes = records
                .get(encoded.value())
                .map_err(storage)?
                .ok_or_else(|| storage("memory index points to a missing record"))?;
            if page.scanned_bytes + bytes.value().len() > self.config.memory.max_scan_bytes {
                if page.scanned == 0 {
                    return Err(Error::Invalid(
                        "record exceeds configured memory scan budget".into(),
                    ));
                }
                break;
            }
            page.scanned += 1;
            page.scanned_bytes += bytes.value().len();
            let record = decode(bytes.value())?;
            let memory =
                parse(&record.value)?.ok_or_else(|| storage("invalid memory index target"))?;
            let matches = !expired(&record, now)
                && query
                    .tag
                    .as_ref()
                    .is_none_or(|tag| memory.tags.contains(tag))
                && query.query.as_ref().is_none_or(|text| {
                    let content = memory.content.to_lowercase();
                    text.split_whitespace().all(|word| content.contains(word))
                });
            if matches {
                let (_, key) = encoded
                    .value()
                    .split_once('\0')
                    .ok_or_else(|| storage("invalid memory index key"))?;
                page.items.push(hit(key, record, memory));
                page.next_cursor = Some(make_cursor(index_key.value())?);
                if serde_json::to_vec(&page).map_err(storage)?.len() > query.max_bytes {
                    page.items.pop();
                    if page.items.is_empty() {
                        return Err(Error::Invalid(
                            "memory and cursor exceed max_bytes; increase the result budget".into(),
                        ));
                    }
                    // Retry this candidate on the next page, even if it was scanned.
                    break;
                }
            }
            last = Some(index_key.value().to_owned());
            if page.items.len() == query.limit {
                if candidates.peek().is_none() {
                    page.next_cursor = None;
                    return Ok(page);
                }
                break;
            }
            if candidates.peek().is_none() {
                page.next_cursor = None;
                return Ok(page);
            }
        }
        page.next_cursor = last.as_deref().map(make_cursor).transpose()?;
        if page.scanned == 0 {
            page.next_cursor = None;
        }
        if serde_json::to_vec(&page).map_err(storage)?.len() > query.max_bytes {
            return Err(Error::Invalid(
                "response exceeds max_bytes; increase the result budget".into(),
            ));
        }
        Ok(page)
    }
}
