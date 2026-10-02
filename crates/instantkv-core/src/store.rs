use crate::{
    clock::{Clock, SystemClock},
    config::{Config, Namespace, OnFull, Purpose, StorageMode, ValueKind},
    error::{Error, Result, storage},
    model::*,
};
use redb::{Database, ReadableDatabase, ReadableTable, Table, TableDefinition};
use std::{
    collections::{BTreeMap, BTreeSet, HashMap, HashSet},
    sync::{Arc, Mutex},
};

pub(crate) const RECORDS: TableDefinition<&str, &[u8]> = TableDefinition::new("records_v1");
const USAGE: TableDefinition<&str, &[u8]> = TableDefinition::new("usage_v1");
const EXPIRY: TableDefinition<&str, &str> = TableDefinition::new("expiry_v1");
const META: TableDefinition<&str, &str> = TableDefinition::new("metadata_v1");

pub struct Engine {
    pub config: Config,
    db: Option<Database>,
    memory: HashMap<String, Mutex<MemoryState>>,
    pub(crate) clock: Arc<dyn Clock>,
}

#[derive(Default)]
struct MemoryState {
    entries: BTreeMap<String, MemoryEntry>,
    expiry: BTreeSet<(u64, String, u64)>,
    fifo: BTreeMap<u64, String>,
    usage: Usage,
}

struct MemoryEntry {
    record: Record,
    deadline: Option<u64>,
}

impl Engine {
    pub fn open(config: Config) -> Result<Self> {
        Self::with_clock(config, Arc::new(SystemClock::default()))
    }

    pub fn with_clock(config: Config, clock: Arc<dyn Clock>) -> Result<Self> {
        config.validate().map_err(Error::Invalid)?;
        let path = config.storage.data_dir.join("instantkv.redb");
        let db = if path.exists()
            || config
                .namespaces
                .iter()
                .any(|ns| ns.mode == StorageMode::Durable)
        {
            std::fs::create_dir_all(&config.storage.data_dir).map_err(storage)?;
            let mut builder = Database::builder();
            if let Some(bytes) = config.storage.cache_size_bytes {
                builder.set_cache_size(bytes);
            }
            let database = builder.create(path).map_err(storage)?;
            let txn = database.begin_write().map_err(storage)?;
            {
                let mut meta = txn.open_table(META).map_err(storage)?;
                if let Some(version) = meta.get("format").map_err(storage)?
                    && version.value() != "1"
                {
                    return Err(Error::Storage("unsupported database format".into()));
                }
                let modes: HashMap<_, _> = config
                    .namespaces
                    .iter()
                    .map(|ns| {
                        (
                            format!("namespace:{}", ns.name),
                            format!("{:?}/{:?}", ns.mode, ns.purpose),
                        )
                    })
                    .collect();
                for entry in meta.iter().map_err(storage)? {
                    let (key, value) = entry.map_err(storage)?;
                    if key.value().starts_with("namespace:")
                        && modes.get(key.value()).map(String::as_str) != Some(value.value())
                    {
                        return Err(Error::Invalid(
                            "persisted namespace removal or mode/purpose change requires migration"
                                .into(),
                        ));
                    }
                }
                meta.insert("format", "1").map_err(storage)?;
                for (key, value) in modes {
                    meta.insert(key.as_str(), value.as_str()).map_err(storage)?;
                }
                txn.open_table(RECORDS).map_err(storage)?;
                txn.open_table(USAGE).map_err(storage)?;
                txn.open_table(EXPIRY).map_err(storage)?;
                txn.open_table(crate::memory::INDEX).map_err(storage)?;
            }
            txn.commit().map_err(storage)?;
            Some(database)
        } else {
            None
        };
        let memory = config
            .namespaces
            .iter()
            .filter(|ns| ns.mode == StorageMode::Memory)
            .map(|ns| (ns.name.clone(), Mutex::new(MemoryState::default())))
            .collect();
        Ok(Self {
            config,
            db,
            memory,
            clock,
        })
    }

    pub fn namespace(&self, name: &str) -> Result<&Namespace> {
        self.config
            .namespaces
            .iter()
            .find(|ns| ns.name == name)
            .ok_or(Error::NamespaceNotFound)
    }

    fn record_namespace(&self, name: &str, key: &str) -> Result<&Namespace> {
        let ns = self.namespace(name)?;
        if ns.purpose != Purpose::Records {
            return Err(Error::Invalid(
                "use checkpoint/restore operations for this namespace".into(),
            ));
        }
        validate_key(ns, key)?;
        if key.starts_with("__") {
            return Err(Error::Invalid(
                "keys beginning with '__' are reserved".into(),
            ));
        }
        Ok(ns)
    }

    pub(crate) fn database(&self) -> Result<&Database> {
        self.db
            .as_ref()
            .ok_or_else(|| Error::Storage("durable storage unavailable".into()))
    }

    pub fn get(&self, namespace: &str, key: &str) -> Result<Record> {
        let ns = self.record_namespace(namespace, key)?;
        if ns.mode == StorageMode::Memory {
            let state = self.memory[namespace].lock().map_err(storage)?;
            let entry = state.entries.get(key).ok_or(Error::NotFound)?;
            if entry
                .deadline
                .is_some_and(|deadline| deadline <= self.clock.tick_ms())
            {
                return Err(Error::NotFound);
            }
            return Ok(entry.record.clone());
        }
        let txn = self.database()?.begin_read().map_err(storage)?;
        let table = txn.open_table(RECORDS).map_err(storage)?;
        let encoded = composite(namespace, key);
        let bytes = table
            .get(encoded.as_str())
            .map_err(storage)?
            .ok_or(Error::NotFound)?;
        let record = decode(bytes.value())?;
        if expired(&record, self.clock.unix_ms()) {
            return Err(Error::NotFound);
        }
        Ok(record)
    }

    pub fn put(
        &self,
        namespace: &str,
        key: &str,
        value: Vec<u8>,
        ttl_seconds: Option<u64>,
        condition: Condition,
    ) -> Result<Record> {
        let ns = self.record_namespace(namespace, key)?;
        validate_value(ns, &value)?;
        if crate::memory::parse(&value)?.is_some() {
            if ns.mode != StorageMode::Durable
                || !matches!(ns.admission.value_kind, ValueKind::Json)
            {
                return Err(Error::Invalid(
                    "structured memory requires a durable JSON records namespace".into(),
                ));
            }
            if key.len() > 256 {
                return Err(Error::Invalid(
                    "structured memory keys may use at most 256 bytes".into(),
                ));
            }
        }
        let ttl = resolve_ttl(ns, ttl_seconds)?;
        let now = self.clock.unix_ms();
        let expires = ttl
            .map(|ttl| {
                now.checked_add(ttl)
                    .ok_or_else(|| Error::Invalid("expiry overflow".into()))
            })
            .transpose()?;
        if ns.mode == StorageMode::Memory {
            let tick = self.clock.tick_ms();
            let deadline = ttl
                .map(|ttl| {
                    tick.checked_add(ttl)
                        .ok_or_else(|| Error::Invalid("deadline overflow".into()))
                })
                .transpose()?;
            let mut state = self.memory[namespace].lock().map_err(storage)?;
            state.cleanup(tick, self.config.storage.cleanup_batch_entries as usize)?;
            let old = state.entries.get(key).map(|entry| entry.record.clone());
            let live = state
                .entries
                .get(key)
                .filter(|entry| !entry.deadline.is_some_and(|deadline| deadline <= tick))
                .map(|entry| entry.record.clone());
            check_condition(condition, live.as_ref())?;
            let mut usage = replace_usage(&state.usage, key, old.as_ref(), &value)?;
            let mut evictions = Vec::new();
            if !fits(ns, &usage) && ns.capacity.on_full == OnFull::EvictOldest {
                for victim in state.fifo.values().filter(|victim| victim.as_str() != key) {
                    let entry = &state.entries[victim];
                    usage.entries -= 1;
                    usage.bytes -= footprint(victim, &entry.record.value)?;
                    evictions.push(victim.clone());
                    if fits(ns, &usage) {
                        break;
                    }
                }
            }
            if !fits(ns, &usage) {
                return Err(Error::Quota);
            }
            let record = Record {
                value,
                revision: usage.revision,
                written_at_ms: now,
                expires_at_ms: expires,
                inserted: live
                    .as_ref()
                    .map_or(usage.revision, |record| record.inserted),
            };
            for victim in evictions {
                state.remove(&victim)?;
            }
            state.remove(key)?;
            if let Some(deadline) = deadline {
                state.expiry.insert((deadline, key.into(), record.revision));
            }
            state.fifo.insert(record.inserted, key.into());
            state.entries.insert(
                key.into(),
                MemoryEntry {
                    record: record.clone(),
                    deadline,
                },
            );
            state.usage = usage;
            return Ok(record);
        }
        let txn = self.database()?.begin_write().map_err(storage)?;
        let result;
        {
            let mut records = txn.open_table(RECORDS).map_err(storage)?;
            let mut expiry = txn.open_table(EXPIRY).map_err(storage)?;
            let mut counters = txn.open_table(USAGE).map_err(storage)?;
            let mut usage = load_usage(&counters, namespace)?;
            let old = read_write(&records, &composite(namespace, key))?;
            result = write_record(
                ns,
                &mut records,
                &mut expiry,
                &mut usage,
                key,
                value,
                now,
                expires,
                condition,
            )?;
            let mut index = txn.open_table(crate::memory::INDEX).map_err(storage)?;
            crate::memory::update_index(&mut index, namespace, key, old.as_ref(), Some(&result))?;
            counters
                .insert(namespace, encode_usage(&usage).as_slice())
                .map_err(storage)?;
        }
        txn.commit().map_err(storage)?;
        Ok(result)
    }

    pub fn delete(&self, namespace: &str, key: &str, condition: Condition) -> Result<()> {
        self.delete_impl(namespace, key, condition, false)
    }

    pub fn forget(&self, namespace: &str, key: &str, condition: Condition) -> Result<()> {
        self.delete_impl(namespace, key, condition, true)
    }

    fn delete_impl(
        &self,
        namespace: &str,
        key: &str,
        condition: Condition,
        managed_only: bool,
    ) -> Result<()> {
        let ns = self.record_namespace(namespace, key)?;
        if ns.mode == StorageMode::Memory {
            if managed_only {
                return Err(Error::Invalid(
                    "structured memory requires durable storage".into(),
                ));
            }
            let mut state = self.memory[namespace].lock().map_err(storage)?;
            let entry = state.entries.get(key).ok_or(Error::NotFound)?;
            if entry
                .deadline
                .is_some_and(|deadline| deadline <= self.clock.tick_ms())
            {
                return Err(Error::NotFound);
            }
            check_condition(condition, Some(&entry.record))?;
            state.remove(key)?;
            return Ok(());
        }
        let txn = self.database()?.begin_write().map_err(storage)?;
        {
            let mut records = txn.open_table(RECORDS).map_err(storage)?;
            let mut expiry = txn.open_table(EXPIRY).map_err(storage)?;
            let mut counters = txn.open_table(USAGE).map_err(storage)?;
            let encoded = composite(namespace, key);
            let record = read_write(&records, &encoded)?.ok_or(Error::NotFound)?;
            if managed_only && crate::memory::parse(&record.value)?.is_none() {
                return Err(Error::NotFound);
            }
            if expired(&record, self.clock.unix_ms()) {
                return Err(Error::NotFound);
            }
            check_condition(condition, Some(&record))?;
            let mut index = txn.open_table(crate::memory::INDEX).map_err(storage)?;
            crate::memory::update_index(&mut index, namespace, key, Some(&record), None)?;
            let mut usage = load_usage(&counters, namespace)?;
            subtract(&mut usage, key, &record)?;
            records.remove(encoded.as_str()).map_err(storage)?;
            if record.expires_at_ms.is_some() {
                expiry
                    .remove(expiry_key(&encoded, &record).as_str())
                    .map_err(storage)?;
            }
            counters
                .insert(namespace, encode_usage(&usage).as_slice())
                .map_err(storage)?;
        }
        txn.commit().map_err(storage)?;
        Ok(())
    }

    pub fn usage(&self, namespace: &str) -> Result<Usage> {
        let ns = self.namespace(namespace)?;
        if ns.mode == StorageMode::Memory {
            return Ok(self.memory[namespace]
                .lock()
                .map_err(storage)?
                .usage
                .clone());
        }
        let txn = self.database()?.begin_read().map_err(storage)?;
        let counters = txn.open_table(USAGE).map_err(storage)?;
        counters
            .get(namespace)
            .map_err(storage)?
            .map(|bytes| decode_usage(bytes.value()))
            .transpose()
            .map(|usage| usage.unwrap_or_default())
    }

    pub fn list(
        &self,
        namespace: &str,
        prefix: &str,
        cursor: Option<&str>,
        limit: usize,
    ) -> Result<Page> {
        let ns = self.namespace(namespace)?;
        if prefix.len() > ns.admission.max_key_bytes as usize
            || cursor.is_some_and(|cursor| cursor.len() > ns.admission.max_key_bytes as usize)
            || !(1..=1000).contains(&limit)
        {
            return Err(Error::Invalid(
                "invalid prefix, cursor, or list limit (1..1000)".into(),
            ));
        }
        let start = cursor.unwrap_or(prefix);
        if cursor.is_some_and(|cursor| !cursor.starts_with(prefix)) {
            return Err(Error::Invalid("cursor must belong to prefix".into()));
        }
        let mut items = Vec::new();
        // Bound scanned entries as well as output, so an expiry backlog cannot stall a request.
        let scan_limit = limit.saturating_mul(4).max(100);
        let mut next_cursor = None;
        if ns.mode == StorageMode::Memory {
            let state = self.memory[namespace].lock().map_err(storage)?;
            for (key, entry) in state.entries.range(start.to_owned()..).take(scan_limit) {
                if !key.starts_with(prefix) {
                    break;
                }
                if cursor == Some(key.as_str()) {
                    continue;
                }
                next_cursor = Some(key.clone());
                if !entry
                    .deadline
                    .is_some_and(|deadline| deadline <= self.clock.tick_ms())
                {
                    items.push(info(key, &entry.record));
                }
                if items.len() == limit {
                    break;
                }
            }
        } else {
            let txn = self.database()?.begin_read().map_err(storage)?;
            let records = txn.open_table(RECORDS).map_err(storage)?;
            let encoded_start = composite(namespace, start);
            let encoded_prefix = composite(namespace, prefix);
            for entry in records
                .range(encoded_start.as_str()..)
                .map_err(storage)?
                .take(scan_limit)
            {
                let (key, bytes) = entry.map_err(storage)?;
                if !key.value().starts_with(&encoded_prefix) {
                    break;
                }
                let key = key
                    .value()
                    .split_once('\0')
                    .ok_or_else(|| storage("invalid record key"))?
                    .1;
                if cursor == Some(key) {
                    continue;
                }
                next_cursor = Some(key.into());
                let record = decode(bytes.value())?;
                if !expired(&record, self.clock.unix_ms()) {
                    items.push(info(key, &record));
                }
                if items.len() == limit {
                    break;
                }
            }
        }
        // A final empty page is permitted. Cursor always advances, including across expired rows.
        Ok(Page { items, next_cursor })
    }

    pub fn checkpoint(
        &self,
        namespace: &str,
        request: &CheckpointRequest,
    ) -> Result<CheckpointReceipt> {
        let ns = self.checkpoint_namespace(namespace)?;
        for name in [&request.id, &request.agent_id, &request.session_id] {
            validate_id(name)?;
        }
        if request.capsule.goal.trim().is_empty()
            || request.capsule.summary.trim().is_empty()
            || request.capsule.next_action.trim().is_empty()
        {
            return Err(Error::Invalid(
                "goal, summary, and next_action must be nonempty".into(),
            ));
        }
        if serde_json::to_vec(&request.capsule).map_err(storage)?.len() > 16384
            || request.references.len() > 64
        {
            return Err(Error::Invalid(
                "capsule exceeds 16 KiB or references exceed 64".into(),
            ));
        }
        for reference in &request.references {
            self.record_namespace(&reference.namespace, &reference.key)?;
            if reference.revision == 0 {
                return Err(Error::Invalid("reference revision must be positive".into()));
            }
        }
        let value = serde_json::to_vec(request).map_err(storage)?;
        validate_value(ns, &value)?;
        let key = format!("__checkpoint/{}", request.id);
        let latest = format!("__latest/{}/{}", request.agent_id, request.session_id);
        validate_key(ns, &key)?;
        validate_key(ns, &latest)?;
        let txn = self.database()?.begin_write().map_err(storage)?;
        let receipt;
        {
            let mut records = txn.open_table(RECORDS).map_err(storage)?;
            let mut expiry = txn.open_table(EXPIRY).map_err(storage)?;
            let mut counters = txn.open_table(USAGE).map_err(storage)?;
            let latest_record = read_write(&records, &composite(namespace, &latest))?;
            if let Some(existing) = read_write(&records, &composite(namespace, &key))? {
                if existing.value != value {
                    return Err(Error::Conflict);
                }
                let latest_record =
                    latest_record.ok_or_else(|| storage("checkpoint latest pointer is missing"))?;
                return Ok(CheckpointReceipt {
                    id: request.id.clone(),
                    revision: existing.revision,
                    latest_revision: latest_record.revision,
                    locator: format!("instantkv://{namespace}/checkpoints/{}", request.id),
                    is_latest: latest_record.value == request.id.as_bytes(),
                });
            }
            let condition = request
                .expected_latest_revision
                .map_or(Condition::Absent, Condition::Revision);
            check_condition(condition, latest_record.as_ref())?;
            let mut usage = load_usage(&counters, namespace)?;
            let now = self.clock.unix_ms();
            let record = write_record(
                ns,
                &mut records,
                &mut expiry,
                &mut usage,
                &key,
                value,
                now,
                None,
                Condition::Absent,
            )?;
            let pointer = write_record(
                ns,
                &mut records,
                &mut expiry,
                &mut usage,
                &latest,
                request.id.as_bytes().to_vec(),
                now,
                None,
                condition,
            )?;
            counters
                .insert(namespace, encode_usage(&usage).as_slice())
                .map_err(storage)?;
            receipt = CheckpointReceipt {
                id: request.id.clone(),
                revision: record.revision,
                latest_revision: pointer.revision,
                locator: format!("instantkv://{namespace}/checkpoints/{}", request.id),
                is_latest: true,
            };
        }
        txn.commit().map_err(storage)?;
        Ok(receipt)
    }

    /// Reclaim an old immutable bundle. The session's latest bundle is protected.
    pub fn delete_checkpoint(&self, namespace: &str, id: &str) -> Result<()> {
        self.checkpoint_namespace(namespace)?;
        validate_id(id)?;
        let key = format!("__checkpoint/{id}");
        let encoded = composite(namespace, &key);
        let txn = self.database()?.begin_write().map_err(storage)?;
        {
            let mut records = txn.open_table(RECORDS).map_err(storage)?;
            let mut counters = txn.open_table(USAGE).map_err(storage)?;
            let record = read_write(&records, &encoded)?.ok_or(Error::NotFound)?;
            let request: CheckpointRequest =
                serde_json::from_slice(&record.value).map_err(storage)?;
            let latest = composite(
                namespace,
                &format!("__latest/{}/{}", request.agent_id, request.session_id),
            );
            let pointer =
                read_write(&records, &latest)?.ok_or_else(|| storage("missing latest pointer"))?;
            if pointer.value == id.as_bytes() {
                return Err(Error::Conflict);
            }
            let mut usage = load_usage(&counters, namespace)?;
            subtract(&mut usage, &key, &record)?;
            records.remove(encoded.as_str()).map_err(storage)?;
            counters
                .insert(namespace, encode_usage(&usage).as_slice())
                .map_err(storage)?;
        }
        txn.commit().map_err(storage)?;
        Ok(())
    }

    fn checkpoint_namespace(&self, namespace: &str) -> Result<&Namespace> {
        let ns = self.namespace(namespace)?;
        if ns.purpose != Purpose::Checkpoints {
            return Err(Error::Invalid(
                "namespace purpose must be checkpoints".into(),
            ));
        }
        Ok(ns)
    }

    pub fn restore_latest(
        &self,
        namespace: &str,
        agent: &str,
        session: &str,
        budget: usize,
        allowed: Option<&HashSet<String>>,
    ) -> Result<Restore> {
        self.checkpoint_namespace(namespace)?;
        validate_id(agent)?;
        validate_id(session)?;
        let txn = self.database()?.begin_read().map_err(storage)?;
        let records = txn.open_table(RECORDS).map_err(storage)?;
        let pointer_key = composite(namespace, &format!("__latest/{agent}/{session}"));
        let pointer = records
            .get(pointer_key.as_str())
            .map_err(storage)?
            .ok_or(Error::NotFound)?;
        let pointer = decode(pointer.value())?;
        let id = std::str::from_utf8(&pointer.value).map_err(storage)?;
        self.restore_snapshot(&records, namespace, id, budget, allowed)
    }

    pub fn restore(
        &self,
        namespace: &str,
        id: &str,
        budget: usize,
        allowed: Option<&HashSet<String>>,
    ) -> Result<Restore> {
        self.checkpoint_namespace(namespace)?;
        validate_id(id)?;
        if !(512..=1048576).contains(&budget) {
            return Err(Error::Invalid(
                "restore byte budget must be 512..1048576".into(),
            ));
        }
        let txn = self.database()?.begin_read().map_err(storage)?;
        let records = txn.open_table(RECORDS).map_err(storage)?;
        self.restore_snapshot(&records, namespace, id, budget, allowed)
    }

    fn restore_snapshot(
        &self,
        records: &redb::ReadOnlyTable<&str, &[u8]>,
        namespace: &str,
        id: &str,
        budget: usize,
        allowed: Option<&HashSet<String>>,
    ) -> Result<Restore> {
        if !(512..=1048576).contains(&budget) {
            return Err(Error::Invalid(
                "restore byte budget must be 512..1048576".into(),
            ));
        }
        let key = composite(namespace, &format!("__checkpoint/{id}"));
        let saved = records
            .get(key.as_str())
            .map_err(storage)?
            .ok_or(Error::NotFound)?;
        let saved = decode(saved.value())?;
        let request: CheckpointRequest = serde_json::from_slice(&saved.value).map_err(storage)?;
        let latest = composite(
            namespace,
            &format!("__latest/{}/{}", request.agent_id, request.session_id),
        );
        let pointer = records
            .get(latest.as_str())
            .map_err(storage)?
            .ok_or_else(|| storage("missing latest pointer"))?;
        let latest_revision = decode(pointer.value())?.revision;
        let references = request
            .references
            .into_iter()
            .map(|reference| {
                let status = if allowed
                    .is_some_and(|allowed| !allowed.contains(&reference.namespace))
                {
                    ReferenceStatus::Forbidden
                } else {
                    match self.get(&reference.namespace, &reference.key) {
                        Ok(record) if record.revision == reference.revision => {
                            ReferenceStatus::Available
                        }
                        Ok(_) => ReferenceStatus::Stale,
                        Err(Error::NotFound | Error::NamespaceNotFound) => ReferenceStatus::Missing,
                        Err(error) => return Err(error),
                    }
                };
                Ok(ResolvedReference { reference, status })
            })
            .collect::<Result<Vec<_>>>()?;
        let result = Restore {
            checkpoint_id: id.into(),
            revision: saved.revision,
            latest_revision,
            capsule: request.capsule,
            references,
        };
        if serde_json::to_vec(&result).map_err(storage)?.len() > budget {
            return Err(Error::Invalid(
                "restore exceeds byte budget; request a larger budget".into(),
            ));
        }
        Ok(result)
    }

    pub fn cleanup(&self) -> Result<usize> {
        let limit = self.config.storage.cleanup_batch_entries as usize;
        let mut count = 0;
        for state in self.memory.values() {
            count += state
                .lock()
                .map_err(storage)?
                .cleanup(self.clock.tick_ms(), limit)?;
        }
        if let Some(db) = &self.db {
            let txn = db.begin_write().map_err(storage)?;
            {
                let mut expiry = txn.open_table(EXPIRY).map_err(storage)?;
                let mut records = txn.open_table(RECORDS).map_err(storage)?;
                let mut counters = txn.open_table(USAGE).map_err(storage)?;
                let now = self.clock.unix_ms();
                let end = format!("{now:020}:\u{10ffff}");
                let expired_keys = expiry
                    .range(..=end.as_str())
                    .map_err(storage)?
                    .take(limit)
                    .map(|entry| {
                        let (key, value) = entry.map_err(storage)?;
                        Ok((key.value().to_owned(), value.value().to_owned()))
                    })
                    .collect::<Result<Vec<_>>>()?;
                if expired_keys.is_empty() {
                    return Ok(count);
                }
                for (index_key, encoded) in expired_keys {
                    if let Some(record) = read_write(&records, &encoded)?
                        && expired(&record, now)
                        && expiry_key(&encoded, &record) == index_key
                    {
                        let (namespace, key) = encoded
                            .split_once('\0')
                            .ok_or_else(|| storage("invalid expiry record"))?;
                        let mut usage = load_usage(&counters, namespace)?;
                        let mut index = txn.open_table(crate::memory::INDEX).map_err(storage)?;
                        crate::memory::update_index(
                            &mut index,
                            namespace,
                            key,
                            Some(&record),
                            None,
                        )?;
                        subtract(&mut usage, key, &record)?;
                        counters
                            .insert(namespace, encode_usage(&usage).as_slice())
                            .map_err(storage)?;
                        records.remove(encoded.as_str()).map_err(storage)?;
                        count += 1;
                    }
                    expiry.remove(index_key.as_str()).map_err(storage)?;
                }
            }
            txn.commit().map_err(storage)?;
        }
        Ok(count)
    }
}

impl MemoryState {
    fn remove(&mut self, key: &str) -> Result<()> {
        if let Some(entry) = self.entries.remove(key) {
            subtract(&mut self.usage, key, &entry.record)?;
            self.fifo.remove(&entry.record.inserted);
            if let Some(deadline) = entry.deadline {
                self.expiry
                    .remove(&(deadline, key.into(), entry.record.revision));
            }
        }
        Ok(())
    }

    fn cleanup(&mut self, now: u64, limit: usize) -> Result<usize> {
        let keys: Vec<_> = self
            .expiry
            .iter()
            .take_while(|(deadline, _, _)| *deadline <= now)
            .take(limit)
            .cloned()
            .collect();
        let mut count = 0;
        for (deadline, key, revision) in keys {
            self.expiry.remove(&(deadline, key.clone(), revision));
            if self
                .entries
                .get(&key)
                .is_some_and(|entry| entry.record.revision == revision)
            {
                self.remove(&key)?;
                count += 1;
            }
        }
        Ok(count)
    }
}

pub(crate) fn composite(namespace: &str, key: &str) -> String {
    format!("{namespace}\0{key}")
}
pub(crate) fn expired(record: &Record, now: u64) -> bool {
    record.expires_at_ms.is_some_and(|deadline| deadline <= now)
}
fn expiry_key(encoded: &str, record: &Record) -> String {
    format!(
        "{:020}:{:020}:{encoded}",
        record.expires_at_ms.unwrap_or(0),
        record.revision
    )
}
fn info(key: &str, record: &Record) -> RecordInfo {
    RecordInfo {
        key: key.into(),
        revision: record.revision,
        bytes: record.value.len(),
        expires_at_ms: record.expires_at_ms,
    }
}

pub fn validate_id(name: &str) -> Result<()> {
    if !(1..=64).contains(&name.len())
        || !name
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-')
    {
        return Err(Error::Invalid(
            "IDs must use 1-64 ASCII letters, digits, '_' or '-'".into(),
        ));
    }
    Ok(())
}

fn validate_key(ns: &Namespace, key: &str) -> Result<()> {
    if key.is_empty()
        || key.len() > ns.admission.max_key_bytes as usize
        || key.chars().any(char::is_control)
    {
        return Err(Error::Invalid(
            "key is empty, contains control characters, or exceeds byte limit".into(),
        ));
    }
    Ok(())
}

fn validate_value(ns: &Namespace, value: &[u8]) -> Result<()> {
    if value.len() as u64 > ns.admission.max_value_bytes {
        return Err(Error::Invalid("value exceeds byte limit".into()));
    }
    match ns.admission.value_kind {
        ValueKind::Bytes => (),
        ValueKind::Utf8 => {
            std::str::from_utf8(value).map_err(|_| Error::Invalid("value must be UTF-8".into()))?;
        }
        ValueKind::Json => {
            serde_json::from_slice::<serde_json::Value>(value)
                .map_err(|_| Error::Invalid("value must be valid JSON".into()))?;
        }
    }
    Ok(())
}

fn resolve_ttl(ns: &Namespace, requested: Option<u64>) -> Result<Option<u64>> {
    let ttl = requested.or(ns.retention.default_ttl_seconds);
    if ttl == Some(0)
        || (ttl.is_none() && ns.retention.require_ttl)
        || ttl
            .zip(ns.retention.max_ttl_seconds)
            .is_some_and(|(ttl, maximum)| ttl > maximum)
    {
        return Err(Error::Invalid(
            "TTL is zero, missing, or exceeds maximum".into(),
        ));
    }
    ttl.map(|ttl| {
        ttl.checked_mul(1000)
            .ok_or_else(|| Error::Invalid("TTL overflow".into()))
    })
    .transpose()
}

fn check_condition(condition: Condition, record: Option<&Record>) -> Result<()> {
    match condition {
        Condition::Any => Ok(()),
        Condition::Absent if record.is_none() => Ok(()),
        Condition::Revision(revision)
            if record.is_some_and(|record| record.revision == revision) =>
        {
            Ok(())
        }
        _ => Err(Error::Conflict),
    }
}

fn footprint(key: &str, value: &[u8]) -> Result<u64> {
    (key.len() as u64)
        .checked_add(value.len() as u64)
        .ok_or_else(|| Error::Invalid("size overflow".into()))
}
fn subtract(usage: &mut Usage, key: &str, record: &Record) -> Result<()> {
    usage.entries = usage
        .entries
        .checked_sub(1)
        .ok_or_else(|| storage("entry accounting underflow"))?;
    usage.bytes = usage
        .bytes
        .checked_sub(footprint(key, &record.value)?)
        .ok_or_else(|| storage("byte accounting underflow"))?;
    Ok(())
}
fn replace_usage(usage: &Usage, key: &str, old: Option<&Record>, value: &[u8]) -> Result<Usage> {
    let mut usage = usage.clone();
    if let Some(old) = old {
        subtract(&mut usage, key, old)?;
    }
    usage.entries = usage
        .entries
        .checked_add(1)
        .ok_or_else(|| storage("entry accounting overflow"))?;
    usage.bytes = usage
        .bytes
        .checked_add(footprint(key, value)?)
        .ok_or_else(|| storage("byte accounting overflow"))?;
    usage.revision = usage
        .revision
        .checked_add(1)
        .ok_or_else(|| storage("revision exhausted"))?;
    Ok(usage)
}
fn fits(ns: &Namespace, usage: &Usage) -> bool {
    usage.entries <= ns.capacity.max_entries && usage.bytes <= ns.capacity.max_total_bytes
}

#[allow(clippy::too_many_arguments)]
fn write_record(
    ns: &Namespace,
    records: &mut Table<'_, &str, &[u8]>,
    expiry: &mut Table<'_, &str, &str>,
    usage: &mut Usage,
    key: &str,
    value: Vec<u8>,
    now: u64,
    expires: Option<u64>,
    condition: Condition,
) -> Result<Record> {
    let encoded = composite(&ns.name, key);
    let old = read_write(records, &encoded)?;
    let live = old.as_ref().filter(|record| !expired(record, now));
    check_condition(condition, live)?;
    let updated_usage = replace_usage(usage, key, old.as_ref(), &value)?;
    if !fits(ns, &updated_usage) {
        return Err(Error::Quota);
    }
    let record = Record {
        value,
        revision: updated_usage.revision,
        written_at_ms: now,
        expires_at_ms: expires,
        inserted: live.map_or(updated_usage.revision, |record| record.inserted),
    };
    if let Some(old) = old.filter(|record| record.expires_at_ms.is_some()) {
        expiry
            .remove(expiry_key(&encoded, &old).as_str())
            .map_err(storage)?;
    }
    records
        .insert(encoded.as_str(), encode(&record).as_slice())
        .map_err(storage)?;
    if record.expires_at_ms.is_some() {
        expiry
            .insert(expiry_key(&encoded, &record).as_str(), encoded.as_str())
            .map_err(storage)?;
    }
    *usage = updated_usage;
    Ok(record)
}

fn read_write(records: &Table<'_, &str, &[u8]>, key: &str) -> Result<Option<Record>> {
    records
        .get(key)
        .map_err(storage)?
        .map(|bytes| decode(bytes.value()))
        .transpose()
}
fn load_usage(counters: &Table<'_, &str, &[u8]>, namespace: &str) -> Result<Usage> {
    counters
        .get(namespace)
        .map_err(storage)?
        .map(|bytes| decode_usage(bytes.value()))
        .transpose()
        .map(|usage| usage.unwrap_or_default())
}

fn encode(record: &Record) -> Vec<u8> {
    let mut bytes = Vec::with_capacity(32 + record.value.len());
    for field in [
        record.revision,
        record.written_at_ms,
        record.expires_at_ms.unwrap_or(0),
        record.inserted,
    ] {
        bytes.extend_from_slice(&field.to_le_bytes());
    }
    bytes.extend_from_slice(&record.value);
    bytes
}
pub(crate) fn decode(bytes: &[u8]) -> Result<Record> {
    if bytes.len() < 32 {
        return Err(storage("truncated record"));
    }
    let field = |offset| {
        u64::from_le_bytes(
            bytes[offset..offset + 8]
                .try_into()
                .expect("checked record header"),
        )
    };
    Ok(Record {
        value: bytes[32..].into(),
        revision: field(0),
        written_at_ms: field(8),
        expires_at_ms: (field(16) != 0).then(|| field(16)),
        inserted: field(24),
    })
}
fn encode_usage(usage: &Usage) -> Vec<u8> {
    [
        usage.entries.to_le_bytes(),
        usage.bytes.to_le_bytes(),
        usage.revision.to_le_bytes(),
    ]
    .concat()
}
fn decode_usage(bytes: &[u8]) -> Result<Usage> {
    if bytes.len() != 24 {
        return Err(storage("invalid usage counter"));
    }
    let field = |offset| {
        u64::from_le_bytes(
            bytes[offset..offset + 8]
                .try_into()
                .expect("checked counter header"),
        )
    };
    Ok(Usage {
        entries: field(0),
        bytes: field(8),
        revision: field(16),
    })
}
