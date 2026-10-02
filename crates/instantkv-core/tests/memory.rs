use instantkv_core::{
    Engine, Error,
    clock::Clock,
    config::{Config, Operation},
    memory::{MemoryInput, MemoryQuery},
    model::Condition,
};
use std::sync::{
    Arc,
    atomic::{AtomicU64, Ordering},
};

struct FakeClock(AtomicU64);
impl Clock for FakeClock {
    fn unix_ms(&self) -> u64 {
        self.0.load(Ordering::SeqCst)
    }
    fn tick_ms(&self) -> u64 {
        self.unix_ms()
    }
}
fn setup() -> (tempfile::TempDir, Config, Arc<FakeClock>) {
    let dir = tempfile::tempdir().unwrap();
    let mut config = Config::parse(include_str!("../../../config/local.toml")).unwrap();
    config.storage.data_dir = dir.path().into();
    (dir, config, Arc::new(FakeClock(AtomicU64::new(10000))))
}
fn input(content: &str, topic: &str, time: u64) -> MemoryInput {
    MemoryInput {
        content: content.into(),
        topic: Some(topic.into()),
        tags: vec!["Local".into(), "local".into()],
        metadata: serde_json::from_value(
            serde_json::json!({"source":"user", "custom":{"confidence":0.8}}),
        )
        .unwrap(),
        occurred_at_ms: Some(time),
    }
}
fn all(engine: &Engine, query: MemoryQuery) -> Vec<String> {
    let mut query = query;
    let mut keys = vec![];
    for _ in 0..100 {
        let page = engine.recall("knowledge", query.clone()).unwrap();
        assert!(serde_json::to_vec(&page).unwrap().len() <= query.max_bytes);
        keys.extend(page.items.into_iter().map(|item| item.key));
        query.cursor = page.next_cursor;
        if query.cursor.is_none() {
            return keys;
        }
    }
    panic!("cursor failed to terminate");
}

#[test]
fn structured_memory_survives_restart_alongside_raw_kv() {
    let (_dir, config, clock) = setup();
    {
        let engine = Engine::with_clock(config.clone(), clock.clone()).unwrap();
        let saved = engine
            .remember(
                "knowledge",
                "prefs/rust",
                input("Prefer Rust", "Preferences", 9000),
                None,
                Condition::Absent,
            )
            .unwrap();
        assert_eq!(saved.memory.topic.as_deref(), Some("preferences"));
        assert_eq!(saved.memory.tags, ["local"]);
        assert_eq!(saved.memory.metadata["custom"]["confidence"], 0.8);
        assert_eq!(saved.written_at_ms, 10000);
        engine
            .put(
                "knowledge",
                "raw",
                br#"{"content":"legacy"}"#.to_vec(),
                None,
                Condition::Any,
            )
            .unwrap();
    }
    let engine = Engine::with_clock(config, clock).unwrap();
    assert_eq!(all(&engine, MemoryQuery::default()), ["prefs/rust"]);
    assert_eq!(
        engine
            .memory_get("knowledge", "prefs/rust")
            .unwrap()
            .memory
            .content,
        "Prefer Rust"
    );
    assert!(matches!(
        engine.memory_get("knowledge", "raw"),
        Err(Error::NotFound)
    ));
    assert_eq!(
        engine.get("knowledge", "raw").unwrap().value,
        br#"{"content":"legacy"}"#
    );
    assert!(matches!(
        engine.forget("knowledge", "raw", Condition::Any),
        Err(Error::NotFound)
    ));
}

#[test]
fn indexed_filters_are_inclusive_and_pages_handle_time_ties() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config, clock).unwrap();
    for (key, topic, time) in [
        ("a", "preferences", 1),
        ("z", "preferences", 2),
        ("😀", "preferences", 2),
        ("other", "work", 3),
    ] {
        engine
            .remember(
                "knowledge",
                key,
                input("Rust local memory", topic, time),
                None,
                Condition::Absent,
            )
            .unwrap();
    }
    let query = MemoryQuery {
        topic: Some(" PREFERENCES ".into()),
        tag: Some("LOCAL".into()),
        query: Some("rust MEMORY".into()),
        since_ms: Some(2),
        until_ms: Some(2),
        limit: 1,
        ..Default::default()
    };
    assert_eq!(all(&engine, query.clone()), ["😀", "z"]);
    let page = engine.recall("knowledge", query.clone()).unwrap();
    let mut changed = query;
    changed.cursor = page.next_cursor;
    changed.topic = Some("work".into());
    assert!(matches!(
        engine.recall("knowledge", changed),
        Err(Error::Invalid(_))
    ));
    assert_eq!(
        all(
            &engine,
            MemoryQuery {
                tag: Some("missing".into()),
                ..Default::default()
            }
        ),
        Vec::<String>::new()
    );
}

#[test]
fn edits_raw_replacements_deletes_and_conflicts_keep_indexes_consistent() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config, clock).unwrap();
    let saved = engine
        .remember(
            "knowledge",
            "fact",
            input("old", "old", 1),
            None,
            Condition::Absent,
        )
        .unwrap();
    assert!(matches!(
        engine.remember(
            "knowledge",
            "fact",
            input("bad", "wrong", 4),
            None,
            Condition::Absent
        ),
        Err(Error::Conflict)
    ));
    assert!(matches!(
        engine.remember(
            "knowledge",
            "fact",
            input("bad", "wrong", 4),
            None,
            Condition::Revision(99)
        ),
        Err(Error::Conflict)
    ));
    let mut replacement = input("new", "new", 2);
    replacement.tags = vec!["newtag".into()];
    let new = engine
        .remember(
            "knowledge",
            "fact",
            replacement,
            None,
            Condition::Revision(saved.revision),
        )
        .unwrap();
    assert!(
        all(
            &engine,
            MemoryQuery {
                tag: Some("local".into()),
                ..Default::default()
            }
        )
        .is_empty()
    );
    assert_eq!(
        all(
            &engine,
            MemoryQuery {
                tag: Some("newtag".into()),
                ..Default::default()
            }
        ),
        ["fact"]
    );
    assert!(
        all(
            &engine,
            MemoryQuery {
                topic: Some("old".into()),
                ..Default::default()
            }
        )
        .is_empty()
    );
    assert_eq!(
        all(
            &engine,
            MemoryQuery {
                topic: Some("new".into()),
                ..Default::default()
            }
        ),
        ["fact"]
    );
    assert!(matches!(
        engine.forget("knowledge", "fact", Condition::Revision(saved.revision)),
        Err(Error::Conflict)
    ));
    engine
        .forget("knowledge", "fact", Condition::Revision(new.revision))
        .unwrap();
    assert!(all(&engine, MemoryQuery::default()).is_empty());
    engine
        .remember(
            "knowledge",
            "fact",
            input("again", "new", 3),
            None,
            Condition::Absent,
        )
        .unwrap();
    engine
        .put("knowledge", "fact", b"{}".to_vec(), None, Condition::Any)
        .unwrap();
    assert!(all(&engine, MemoryQuery::default()).is_empty());
    let managed = engine
        .remember(
            "knowledge",
            "other",
            input("value", "raw", 7),
            None,
            Condition::Absent,
        )
        .unwrap();
    let bytes = engine.get("knowledge", "other").unwrap().value;
    engine
        .put("knowledge", "copy", bytes, None, Condition::Absent)
        .unwrap();
    engine
        .delete("knowledge", "other", Condition::Revision(managed.revision))
        .unwrap();
    assert_eq!(all(&engine, MemoryQuery::default()), ["copy"]);
}

#[test]
fn expired_memories_are_hidden_and_cleanup_removes_their_indexes() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config, clock.clone()).unwrap();
    engine
        .remember(
            "knowledge",
            "expiry",
            input("temporary", "notes", 1),
            Some(1),
            Condition::Absent,
        )
        .unwrap();
    clock.0.store(11000, Ordering::SeqCst);
    let page = engine.recall("knowledge", MemoryQuery::default()).unwrap();
    assert!(page.items.is_empty());
    assert_eq!(page.scanned, 1);
    assert!(matches!(
        engine.memory_get("knowledge", "expiry"),
        Err(Error::NotFound)
    ));
    assert_eq!(engine.cleanup().unwrap(), 1);
    assert_eq!(
        engine
            .recall("knowledge", MemoryQuery::default())
            .unwrap()
            .scanned,
        0
    );
    assert_eq!(
        engine
            .recall(
                "knowledge",
                MemoryQuery {
                    tag: Some("local".into()),
                    ..Default::default()
                }
            )
            .unwrap()
            .scanned,
        0
    );
}

#[test]
fn bounded_keyword_scans_can_return_empty_pages_without_losing_matches() {
    let (_dir, mut config, clock) = setup();
    config.memory.max_candidates = 2;
    let engine = Engine::with_clock(config, clock).unwrap();
    for n in 0..7 {
        engine
            .remember(
                "knowledge",
                &n.to_string(),
                input(if n == 0 { "needle" } else { "other" }, "notes", n),
                None,
                Condition::Absent,
            )
            .unwrap();
    }
    let query = MemoryQuery {
        query: Some("needle".into()),
        ..Default::default()
    };
    let first = engine.recall("knowledge", query.clone()).unwrap();
    assert!(first.items.is_empty());
    assert!(first.next_cursor.is_some());
    assert_eq!(first.scanned, 2);
    assert_eq!(all(&engine, query), ["0"]);
}

#[test]
fn response_and_scan_bytes_are_bounded_and_retry_the_unreturned_candidate() {
    let (_dir, mut config, clock) = setup();
    config.memory.max_scan_bytes = 65536;
    let engine = Engine::with_clock(config, clock).unwrap();
    for n in 0..6 {
        engine
            .remember(
                "knowledge",
                &n.to_string(),
                input(&"x".repeat(600), "notes", n),
                None,
                Condition::Absent,
            )
            .unwrap();
    }
    assert_eq!(
        all(
            &engine,
            MemoryQuery {
                max_bytes: 1700,
                ..Default::default()
            }
        ),
        ["5", "4", "3", "2", "1", "0"]
    );
    assert!(matches!(
        engine.recall(
            "knowledge",
            MemoryQuery {
                max_bytes: 1024,
                ..Default::default()
            }
        ),
        Err(Error::Invalid(_))
    ));
    for n in 6..10 {
        let mut value = input(&"x".repeat(16000), "large", n);
        value
            .metadata
            .insert("blob".into(), serde_json::json!("z".repeat(8000)));
        engine
            .remember("knowledge", &n.to_string(), value, None, Condition::Absent)
            .unwrap();
    }
    let page = engine
        .recall(
            "knowledge",
            MemoryQuery {
                topic: Some("large".into()),
                query: Some("absent".into()),
                ..Default::default()
            },
        )
        .unwrap();
    assert_eq!(page.scanned, 2);
    assert!(page.scanned_bytes <= 65536);
    assert!(page.next_cursor.is_some());
}

#[test]
fn invalid_memory_and_quota_failures_leave_no_index_entries() {
    let (_dir, mut config, clock) = setup();
    config.namespaces[0].capacity.max_entries = 1;
    config.namespaces[0].admission.max_key_bytes = 1024;
    let engine = Engine::with_clock(config, clock).unwrap();
    assert!(matches!(
        engine.remember(
            "knowledge",
            &"x".repeat(257),
            input("bad", "notes", 0),
            None,
            Condition::Absent
        ),
        Err(Error::Invalid(_))
    ));
    engine
        .remember(
            "knowledge",
            "one",
            input("valid", "notes", 1),
            None,
            Condition::Absent,
        )
        .unwrap();
    assert!(matches!(
        engine.remember(
            "knowledge",
            "two",
            input("overquota", "notes", 2),
            None,
            Condition::Absent
        ),
        Err(Error::Quota)
    ));
    let mut bad = input("bad", "notes", 3);
    bad.tags = vec!["tag".into(); 9];
    assert!(matches!(
        engine.remember("knowledge", "one", bad, None, Condition::Any),
        Err(Error::Invalid(_))
    ));
    assert!(matches!(
        engine.put(
            "knowledge",
            "one",
            br#"{"_instantkv_memory":1}"#.to_vec(),
            None,
            Condition::Any
        ),
        Err(Error::Invalid(_))
    ));
    assert!(matches!(
        engine.remember(
            "scratch",
            "one",
            input("bad", "notes", 3),
            None,
            Condition::Absent
        ),
        Err(Error::Invalid(_))
    ));
    assert_eq!(all(&engine, MemoryQuery::default()), ["one"]);
    assert_eq!(
        engine
            .memory_get("knowledge", "one")
            .unwrap()
            .memory
            .content,
        "valid"
    );
    for query in [
        MemoryQuery {
            limit: 0,
            ..Default::default()
        },
        MemoryQuery {
            since_ms: Some(9),
            until_ms: Some(1),
            ..Default::default()
        },
        MemoryQuery {
            max_bytes: 65537,
            ..Default::default()
        },
    ] {
        assert!(matches!(
            engine.recall("knowledge", query),
            Err(Error::Invalid(_))
        ));
    }
    // Preserve the pre-existing configuration format and permission enum.
    assert_eq!(
        engine.config.auth.principals[0].operations[0],
        Operation::Get
    );
}

#[test]
fn concurrent_updates_and_reads_observe_consistent_records_and_indexes() {
    let (_dir, config, clock) = setup();
    let engine = Arc::new(Engine::with_clock(config, clock).unwrap());
    engine
        .remember(
            "knowledge",
            "shared",
            input("value", "a", 1),
            None,
            Condition::Absent,
        )
        .unwrap();
    let writer = engine.clone();
    let task = std::thread::spawn(move || {
        for n in 2..40 {
            writer
                .remember(
                    "knowledge",
                    "shared",
                    input("value", if n % 2 == 0 { "a" } else { "b" }, n),
                    None,
                    Condition::Any,
                )
                .unwrap();
        }
    });
    for _ in 0..100 {
        let page = engine.recall("knowledge", MemoryQuery::default()).unwrap();
        assert_eq!(page.items.len(), 1);
        for topic in ["a", "b"] {
            let page = engine
                .recall(
                    "knowledge",
                    MemoryQuery {
                        topic: Some(topic.into()),
                        ..Default::default()
                    },
                )
                .unwrap();
            assert!(
                page.items
                    .iter()
                    .all(|item| item.memory.topic.as_deref() == Some(topic))
            );
        }
    }
    task.join().unwrap();
}
