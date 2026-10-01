use instantkv_core::{
    Engine, Error,
    clock::Clock,
    config::{Config, OnFull},
    model::{Capsule, CheckpointRequest, Condition, MemoryReference, ReferenceStatus},
};
use std::sync::{
    Arc,
    atomic::{AtomicU64, Ordering},
};

#[derive(Default)]
struct FakeClock {
    wall: AtomicU64,
    tick: AtomicU64,
}
impl Clock for FakeClock {
    fn unix_ms(&self) -> u64 {
        self.wall.load(Ordering::SeqCst)
    }
    fn tick_ms(&self) -> u64 {
        self.tick.load(Ordering::SeqCst)
    }
}
impl FakeClock {
    fn advance(&self, ms: u64) {
        self.wall.fetch_add(ms, Ordering::SeqCst);
        self.tick.fetch_add(ms, Ordering::SeqCst);
    }
}

fn setup() -> (tempfile::TempDir, Config, Arc<FakeClock>) {
    let dir = tempfile::tempdir().unwrap();
    let mut config = Config::parse(include_str!("../../../config/instantkv.example.toml")).unwrap();
    config.storage.data_dir = dir.path().into();
    let clock = Arc::new(FakeClock::default());
    clock.advance(10000);
    (dir, config, clock)
}

fn checkpoint(id: &str, expected: Option<u64>) -> CheckpointRequest {
    CheckpointRequest {
        id: id.into(),
        agent_id: "demo-agent".into(),
        session_id: "task-1".into(),
        expected_latest_revision: expected,
        capsule: Capsule {
            goal: "Ship instantKV".into(),
            summary: "Storage choice is committed.".into(),
            constraints: vec!["Keep secrets server-side".into()],
            decisions: vec!["Use Rust and redb".into()],
            open_tasks: vec!["Add MCP tools".into()],
            next_action: "Implement the HTTP routes".into(),
        },
        references: vec![],
    }
}

#[test]
fn durable_records_and_checkpoint_survive_reopen() {
    let (_dir, config, clock) = setup();
    let receipt;
    {
        let engine = Engine::with_clock(config.clone(), clock.clone()).unwrap();
        engine
            .put(
                "knowledge",
                "decision/storage",
                br#"{"engine":"redb"}"#.to_vec(),
                None,
                Condition::Absent,
            )
            .unwrap();
        receipt = engine
            .checkpoint("checkpoints", &checkpoint("cp-1", None))
            .unwrap();
    }
    let engine = Engine::with_clock(config, clock).unwrap();
    assert_eq!(
        engine.get("knowledge", "decision/storage").unwrap().value,
        br#"{"engine":"redb"}"#
    );
    let restored = engine
        .restore_latest("checkpoints", "demo-agent", "task-1", 32768, None)
        .unwrap();
    assert_eq!(restored.checkpoint_id, "cp-1");
    assert_eq!(restored.latest_revision, receipt.latest_revision);
    assert_eq!(
        restored.capsule.constraints,
        vec!["Keep secrets server-side"]
    );
    assert_eq!(engine.usage("scratch").unwrap().entries, 0);
}

#[test]
fn ttl_boundary_and_overwrite_cleanup_are_correct_in_both_backends() {
    for namespace in ["knowledge", "scratch"] {
        let (_dir, config, clock) = setup();
        let engine = Engine::with_clock(config, clock.clone()).unwrap();
        engine
            .put(namespace, "key", b"1".to_vec(), Some(1), Condition::Any)
            .unwrap();
        clock.advance(999);
        assert!(engine.get(namespace, "key").is_ok());
        engine
            .put(namespace, "key", b"2".to_vec(), Some(10), Condition::Any)
            .unwrap();
        clock.advance(1);
        engine.cleanup().unwrap();
        assert_eq!(engine.get(namespace, "key").unwrap().value, b"2");
        clock.advance(9999);
        assert!(matches!(engine.get(namespace, "key"), Err(Error::NotFound)));
        engine.cleanup().unwrap();
        assert_eq!(engine.usage(namespace).unwrap().entries, 0);
        assert_eq!(engine.usage(namespace).unwrap().bytes, 0);
    }
}

#[test]
fn cache_expiry_uses_monotonic_clock() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config, clock.clone()).unwrap();
    engine
        .put("scratch", "key", b"1".to_vec(), Some(1), Condition::Any)
        .unwrap();
    clock.wall.fetch_add(100000, Ordering::SeqCst);
    assert!(engine.get("scratch", "key").is_ok());
    clock.tick.fetch_add(1000, Ordering::SeqCst);
    assert!(matches!(engine.get("scratch", "key"), Err(Error::NotFound)));
}

#[test]
fn quota_rejection_and_invalid_payload_preserve_old_value() {
    let (_dir, mut config, clock) = setup();
    config.namespaces[0].capacity.max_entries = 1;
    let engine = Engine::with_clock(config, clock).unwrap();
    let old = engine
        .put("knowledge", "key", b"1".to_vec(), None, Condition::Any)
        .unwrap();
    assert!(matches!(
        engine.put("knowledge", "other", b"2".to_vec(), None, Condition::Any),
        Err(Error::Quota)
    ));
    assert!(matches!(
        engine.put(
            "knowledge",
            "key",
            b"broken JSON".to_vec(),
            None,
            Condition::Any
        ),
        Err(Error::Invalid(_))
    ));
    assert!(matches!(
        engine.put(
            "knowledge",
            "key",
            b"3".to_vec(),
            None,
            Condition::Revision(old.revision + 1)
        ),
        Err(Error::Conflict)
    ));
    assert_eq!(engine.get("knowledge", "key").unwrap().value, b"1");
    assert_eq!(engine.usage("knowledge").unwrap().entries, 1);
    assert_eq!(engine.usage("knowledge").unwrap().bytes, 4);
}

#[test]
fn fifo_eviction_does_not_reorder_on_reads_or_overwrites() {
    let (_dir, mut config, clock) = setup();
    config.namespaces[2].capacity.max_entries = 2;
    config.namespaces[2].capacity.on_full = OnFull::EvictOldest;
    let engine = Engine::with_clock(config, clock).unwrap();
    for key in ["a", "b"] {
        engine
            .put("scratch", key, b"1".to_vec(), None, Condition::Any)
            .unwrap();
    }
    engine.get("scratch", "a").unwrap();
    engine
        .put("scratch", "a", b"2".to_vec(), None, Condition::Any)
        .unwrap();
    engine
        .put("scratch", "c", b"3".to_vec(), None, Condition::Any)
        .unwrap();
    assert!(matches!(engine.get("scratch", "a"), Err(Error::NotFound)));
    assert!(engine.get("scratch", "b").is_ok());
    assert_eq!(engine.usage("scratch").unwrap().entries, 2);
    assert_eq!(engine.usage("scratch").unwrap().bytes, 4);
}

#[test]
fn revisions_prevent_delete_recreate_aba() {
    for namespace in ["knowledge", "scratch"] {
        let (_dir, config, clock) = setup();
        let engine = Engine::with_clock(config, clock).unwrap();
        let first = engine
            .put(namespace, "key", b"1".to_vec(), None, Condition::Any)
            .unwrap();
        engine
            .delete(namespace, "key", Condition::Revision(first.revision))
            .unwrap();
        let second = engine
            .put(namespace, "key", b"2".to_vec(), None, Condition::Absent)
            .unwrap();
        assert!(second.revision > first.revision);
        assert!(matches!(
            engine.put(
                namespace,
                "key",
                b"3".to_vec(),
                None,
                Condition::Revision(first.revision)
            ),
            Err(Error::Conflict)
        ));
    }
}

#[test]
fn expired_reinsert_outside_cleanup_batch_is_a_new_fifo_entry() {
    let (_dir, mut config, clock) = setup();
    config.storage.cleanup_batch_entries = 1;
    config.namespaces[2].capacity.max_entries = 3;
    let engine = Engine::with_clock(config, clock.clone()).unwrap();
    for key in ["a", "b"] {
        engine
            .put("scratch", key, b"1".to_vec(), Some(1), Condition::Any)
            .unwrap();
    }
    engine
        .put("scratch", "c", b"1".to_vec(), Some(20), Condition::Any)
        .unwrap();
    clock.advance(1000);
    // The bounded sweep removes a, leaving the expired b for replacement.
    engine
        .put("scratch", "b", b"2".to_vec(), Some(20), Condition::Absent)
        .unwrap();
    for key in ["d", "e"] {
        engine
            .put("scratch", key, b"1".to_vec(), Some(20), Condition::Any)
            .unwrap();
    }
    assert!(matches!(engine.get("scratch", "c"), Err(Error::NotFound)));
    assert_eq!(engine.get("scratch", "b").unwrap().value, b"2");
    assert_eq!(engine.usage("scratch").unwrap().entries, 3);
}

#[test]
fn pruning_old_checkpoints_reclaims_quota_and_protects_latest() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config.clone(), clock.clone()).unwrap();
    let first = engine
        .checkpoint("checkpoints", &checkpoint("cp-1", None))
        .unwrap();
    assert!(matches!(
        engine.delete_checkpoint("checkpoints", "cp-1"),
        Err(Error::Conflict)
    ));
    let second = engine
        .checkpoint(
            "checkpoints",
            &checkpoint("cp-2", Some(first.latest_revision)),
        )
        .unwrap();
    let before = engine.usage("checkpoints").unwrap();
    engine.delete_checkpoint("checkpoints", "cp-1").unwrap();
    let after = engine.usage("checkpoints").unwrap();
    assert_eq!(after.entries, before.entries - 1);
    assert!(after.bytes < before.bytes);
    assert_eq!(after.revision, before.revision);
    assert!(matches!(
        engine.restore("checkpoints", "cp-1", 32768, None),
        Err(Error::NotFound)
    ));
    drop(engine);
    let reopened = Engine::with_clock(config, clock).unwrap();
    assert_eq!(
        reopened
            .restore_latest("checkpoints", "demo-agent", "task-1", 32768, None)
            .unwrap()
            .latest_revision,
        second.latest_revision
    );
}

#[test]
fn checkpoint_is_atomic_when_pointer_would_exceed_quota() {
    let (_dir, mut config, clock) = setup();
    config.namespaces[1].capacity.max_entries = 1;
    let engine = Engine::with_clock(config, clock).unwrap();
    assert!(matches!(
        engine.checkpoint("checkpoints", &checkpoint("cp-1", None)),
        Err(Error::Quota)
    ));
    assert_eq!(engine.usage("checkpoints").unwrap().entries, 0);
    assert!(matches!(
        engine.restore("checkpoints", "cp-1", 32768, None),
        Err(Error::NotFound)
    ));
}

#[test]
fn checkpoint_retries_do_not_rewind_latest_pointer() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config, clock).unwrap();
    let first = checkpoint("cp-1", None);
    let receipt = engine.checkpoint("checkpoints", &first).unwrap();
    let second = checkpoint("cp-2", Some(receipt.latest_revision));
    engine.checkpoint("checkpoints", &second).unwrap();
    assert!(!engine.checkpoint("checkpoints", &first).unwrap().is_latest);
    assert_eq!(
        engine
            .restore_latest("checkpoints", "demo-agent", "task-1", 32768, None)
            .unwrap()
            .checkpoint_id,
        "cp-2"
    );
    let mut changed = first;
    changed.capsule.summary = "conflicting content".into();
    assert!(matches!(
        engine.checkpoint("checkpoints", &changed),
        Err(Error::Conflict)
    ));
    assert!(matches!(
        engine.checkpoint("checkpoints", &checkpoint("cp-3", None)),
        Err(Error::Conflict)
    ));
}

#[test]
fn restore_reports_stale_missing_and_forbidden_references_and_enforces_budget() {
    let (_dir, config, clock) = setup();
    let engine = Engine::with_clock(config, clock).unwrap();
    let record = engine
        .put("knowledge", "key", b"1".to_vec(), None, Condition::Any)
        .unwrap();
    let mut request = checkpoint("cp-1", None);
    request.references = vec![MemoryReference {
        namespace: "knowledge".into(),
        key: "key".into(),
        revision: record.revision,
    }];
    engine.checkpoint("checkpoints", &request).unwrap();
    assert!(matches!(
        engine
            .restore("checkpoints", "cp-1", 32768, None)
            .unwrap()
            .references[0]
            .status,
        ReferenceStatus::Available
    ));
    engine
        .put("knowledge", "key", b"2".to_vec(), None, Condition::Any)
        .unwrap();
    assert!(matches!(
        engine
            .restore("checkpoints", "cp-1", 32768, None)
            .unwrap()
            .references[0]
            .status,
        ReferenceStatus::Stale
    ));
    engine.delete("knowledge", "key", Condition::Any).unwrap();
    assert!(matches!(
        engine
            .restore("checkpoints", "cp-1", 32768, None)
            .unwrap()
            .references[0]
            .status,
        ReferenceStatus::Missing
    ));
    assert!(matches!(
        engine
            .restore("checkpoints", "cp-1", 32768, Some(&Default::default()))
            .unwrap()
            .references[0]
            .status,
        ReferenceStatus::Forbidden
    ));
    assert!(matches!(
        engine.restore("checkpoints", "cp-1", 100, None),
        Err(Error::Invalid(_))
    ));
}

#[test]
fn concurrent_conditional_writers_have_exactly_one_winner() {
    let (_dir, config, clock) = setup();
    let engine = Arc::new(Engine::with_clock(config, clock).unwrap());
    let record = engine
        .put("knowledge", "key", b"1".to_vec(), None, Condition::Any)
        .unwrap();
    let threads: Vec<_> = (0..8)
        .map(|_| {
            let engine = engine.clone();
            std::thread::spawn(move || {
                engine
                    .put(
                        "knowledge",
                        "key",
                        b"2".to_vec(),
                        None,
                        Condition::Revision(record.revision),
                    )
                    .is_ok()
            })
        })
        .collect();
    assert_eq!(
        threads
            .into_iter()
            .map(|thread| thread.join().unwrap())
            .filter(|won| *won)
            .count(),
        1
    );
}

#[test]
fn namespace_mode_changes_are_rejected_after_persistence() {
    let (_dir, config, clock) = setup();
    drop(Engine::with_clock(config.clone(), clock.clone()).unwrap());
    let mut changed = config;
    changed.namespaces[0].mode = instantkv_core::config::StorageMode::Memory;
    assert!(matches!(
        Engine::with_clock(changed, clock),
        Err(Error::Invalid(_))
    ));
}
