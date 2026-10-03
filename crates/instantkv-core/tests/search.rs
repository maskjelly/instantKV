use instantkv_core::{
    Engine, Error, clock::Clock, config::Config, memory::MemoryInput, model::Condition,
    search::SearchQuery,
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
fn input(text: &str, topic: &str, time: u64) -> MemoryInput {
    MemoryInput {
        content: text.into(),
        topic: Some(topic.into()),
        tags: vec!["local".into()],
        occurred_at_ms: Some(time),
        ..Default::default()
    }
}
fn query(text: &str) -> SearchQuery {
    SearchQuery {
        query: text.into(),
        ..Default::default()
    }
}

#[test]
fn ranks_by_relevance_with_stemming_or_terms_and_exact_filters() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config, clock).unwrap();
    engine
        .remember(
            "knowledge",
            "old-relevant",
            input("Antibodies bind immune cells", "science", 1),
            None,
            Condition::Absent,
        )
        .unwrap();
    engine
        .remember(
            "knowledge",
            "new-noise",
            input("Cells need food", "science", 9),
            None,
            Condition::Absent,
        )
        .unwrap();
    engine
        .remember(
            "knowledge",
            "private-topic",
            input("Antibodies bind immune cells", "other", 10),
            None,
            Condition::Absent,
        )
        .unwrap();
    let mut q = query("How does an antibody bind the immune system?");
    q.topic = Some("SCIENCE".into());
    q.tag = Some("LOCAL".into());
    q.since_ms = Some(1);
    q.until_ms = Some(9);
    let page = engine.search("knowledge", q).unwrap();
    assert_eq!(page.items.len(), 1);
    assert_eq!(page.items[0].hit.key, "old-relevant");
    assert!(page.items[0].score > 0.0 && page.items[0].score.is_finite());
    assert!(!page.truncated);
}

#[test]
fn updates_raw_replacement_forget_and_expiry_keep_search_consistent() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config, clock.clone()).unwrap();
    let first = engine
        .remember(
            "knowledge",
            "fact",
            input("Antibodies bind cells", "science", 1),
            None,
            Condition::Absent,
        )
        .unwrap();
    assert!(matches!(
        engine.remember(
            "knowledge",
            "fact",
            input("wrong penguin", "science", 1),
            None,
            Condition::Revision(first.revision + 1)
        ),
        Err(Error::Conflict)
    ));
    assert!(
        engine
            .search("knowledge", query("penguin"))
            .unwrap()
            .items
            .is_empty()
    );
    let next = engine
        .remember(
            "knowledge",
            "fact",
            input("Penguins prefer cold water", "science", 1),
            None,
            Condition::Revision(first.revision),
        )
        .unwrap();
    assert_eq!(
        engine
            .search("knowledge", query("antibody"))
            .unwrap()
            .postings_scanned,
        0
    );
    assert_eq!(
        engine.search("knowledge", query("penguin")).unwrap().items[0]
            .hit
            .key,
        "fact"
    );
    engine
        .put(
            "knowledge",
            "fact",
            br#"{"raw":true}"#.to_vec(),
            None,
            Condition::Revision(next.revision),
        )
        .unwrap();
    assert_eq!(
        engine
            .search("knowledge", query("penguin"))
            .unwrap()
            .postings_scanned,
        0
    );
    let saved = engine
        .remember(
            "knowledge",
            "ttl",
            input("Penguins swim", "science", 2),
            Some(1),
            Condition::Absent,
        )
        .unwrap();
    clock.0.store(11000, Ordering::SeqCst);
    assert!(
        engine
            .search("knowledge", query("penguin"))
            .unwrap()
            .items
            .is_empty()
    );
    engine.cleanup().unwrap();
    assert_eq!(
        engine
            .search("knowledge", query("penguin"))
            .unwrap()
            .postings_scanned,
        0
    );
    clock.0.store(12000, Ordering::SeqCst);
    let saved2 = engine
        .remember(
            "knowledge",
            "ttl",
            input("Penguins swim", "science", 2),
            None,
            Condition::Absent,
        )
        .unwrap();
    assert!(saved2.revision > saved.revision);
    engine
        .forget("knowledge", "ttl", Condition::Revision(saved2.revision))
        .unwrap();
    assert_eq!(
        engine
            .search("knowledge", query("penguin"))
            .unwrap()
            .postings_scanned,
        0
    );
}

#[test]
fn failed_quota_write_does_not_publish_postings() {
    let (_dir, mut config, clock) = setup();
    config
        .namespaces
        .iter_mut()
        .find(|ns| ns.name == "knowledge")
        .unwrap()
        .capacity
        .max_entries = 1;
    let engine = Engine::with_clock(config, clock).unwrap();
    engine
        .remember(
            "knowledge",
            "one",
            input("Rust tools", "work", 1),
            None,
            Condition::Absent,
        )
        .unwrap();
    assert!(matches!(
        engine.remember(
            "knowledge",
            "two",
            input("Penguin tools", "work", 2),
            None,
            Condition::Absent
        ),
        Err(Error::Quota)
    ));
    assert_eq!(
        engine
            .search("knowledge", query("penguin"))
            .unwrap()
            .postings_scanned,
        0
    );
    assert_eq!(
        engine
            .search("knowledge", query("rust"))
            .unwrap()
            .items
            .len(),
        1
    );
}

#[test]
fn cursor_continues_after_restart_and_rejects_changed_filters_or_writes() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config.clone(), clock.clone()).unwrap();
    for key in ["a", "b", "😀"] {
        engine
            .remember(
                "knowledge",
                key,
                input("Rust local tools", "work", 1),
                None,
                Condition::Absent,
            )
            .unwrap();
    }
    let mut q = query("Rust");
    q.limit = 1;
    let page = engine.search("knowledge", q.clone()).unwrap();
    assert_eq!(page.items[0].hit.key, "a");
    q.cursor = page.next_cursor;
    drop(engine);
    let engine = Engine::with_clock(config, clock).unwrap();
    let page = engine.search("knowledge", q.clone()).unwrap();
    assert_eq!(page.items[0].hit.key, "b");
    let mut wrong = q.clone();
    wrong.query = "local".into();
    assert!(engine.search("knowledge", wrong).is_err());
    q.cursor = page.next_cursor;
    let page = engine.search("knowledge", q.clone()).unwrap();
    assert_eq!(page.items[0].hit.key, "😀");
    assert!(page.next_cursor.is_none());
    engine
        .remember(
            "knowledge",
            "new",
            input("Rust tools", "work", 2),
            None,
            Condition::Absent,
        )
        .unwrap();
    assert!(
        engine
            .search("knowledge", q)
            .unwrap_err()
            .to_string()
            .contains("stale")
    );
}

#[test]
fn response_budget_keeps_the_final_overflowing_hit_for_the_next_page() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config, clock).unwrap();
    for key in ["a", "b"] {
        engine
            .remember(
                "knowledge",
                key,
                input(&format!("rust {}", "x".repeat(250)), "work", 1),
                None,
                Condition::Absent,
            )
            .unwrap();
    }
    let mut q = query("rust");
    q.limit = 1;
    q.max_bytes = 65536;
    let size = serde_json::to_vec(&engine.search("knowledge", q.clone()).unwrap())
        .unwrap()
        .len();
    q.limit = 10;
    q.max_bytes = (size + 32).max(1024);
    let first = engine.search("knowledge", q.clone()).unwrap();
    assert_eq!(first.items.len(), 1);
    assert!(first.next_cursor.is_some());
    assert!(serde_json::to_vec(&first).unwrap().len() <= q.max_bytes);
    q.cursor = first.next_cursor;
    let second = engine.search("knowledge", q).unwrap();
    assert_eq!(second.items[0].hit.key, "b");
    assert!(second.next_cursor.is_none());
}

#[test]
fn work_limits_report_truncation_and_candidate_cursor_progresses() {
    let (_dir, mut config, clock) = setup();
    config.memory.max_candidates = 1;
    let engine = Engine::with_clock(config.clone(), clock.clone()).unwrap();
    for (key, topic) in [("a", "other"), ("b", "other"), ("c", "wanted")] {
        engine
            .remember(
                "knowledge",
                key,
                input("Rust tools", topic, 1),
                None,
                Condition::Absent,
            )
            .unwrap();
    }
    let mut q = query("rust");
    q.topic = Some("wanted".into());
    for _ in 0..2 {
        let page = engine.search("knowledge", q.clone()).unwrap();
        assert!(page.items.is_empty() && page.truncated);
        assert_eq!(page.candidates_scanned, 1);
        q.cursor = page.next_cursor;
        assert!(q.cursor.is_some());
    }
    assert_eq!(engine.search("knowledge", q).unwrap().items[0].hit.key, "c");
    drop(engine);
    config.memory.max_search_postings = 1;
    let engine = Engine::with_clock(config, clock).unwrap();
    let page = engine.search("knowledge", query("rust tools")).unwrap();
    assert!(page.truncated);
    assert_eq!(page.postings_scanned, 1);
}

#[test]
fn first_open_backfills_old_memory_without_changing_record_revisions() {
    let (dir, config, clock) = setup();
    let engine = Engine::with_clock(config.clone(), clock.clone()).unwrap();
    let saved = engine
        .remember(
            "knowledge",
            "old",
            input("Antibodies bind cells", "science", 1),
            None,
            Condition::Absent,
        )
        .unwrap();
    engine
        .put(
            "knowledge",
            "raw",
            br#"{"content":"unmanaged"}"#.to_vec(),
            None,
            Condition::Absent,
        )
        .unwrap();
    drop(engine);
    {
        let db = redb::Database::create(dir.path().join("instantkv.redb")).unwrap();
        let txn = db.begin_write().unwrap();
        txn.delete_table(redb::TableDefinition::<&str, (u32, u32)>::new(
            "search_postings_v1",
        ))
        .unwrap();
        txn.delete_table(redb::TableDefinition::<&str, u64>::new("search_terms_v1"))
            .unwrap();
        txn.delete_table(redb::TableDefinition::<&str, (u64, u64, u64)>::new(
            "search_stats_v1",
        ))
        .unwrap();
        txn.commit().unwrap();
    }
    let engine = Engine::with_clock(config, clock).unwrap();
    assert_eq!(
        engine.search("knowledge", query("antibody")).unwrap().items[0]
            .hit
            .revision,
        saved.revision
    );
    assert_eq!(
        engine
            .memory_get("knowledge", "old")
            .unwrap()
            .memory
            .content,
        "Antibodies bind cells"
    );
    assert!(
        engine
            .search("knowledge", query("unmanaged"))
            .unwrap()
            .items
            .is_empty()
    );
}
