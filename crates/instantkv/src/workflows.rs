use anyhow::{Result, bail};
use instantkv::client::Client;
use instantkv_core::{
    memory::{MemoryInput, MemoryQuery, RememberRequest},
    model::{Capsule, CheckpointRequest, MemoryReference},
    search::SearchQuery,
};
use serde_json::json;
use std::{
    path::Path,
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};
use tokio::task::JoinSet;

fn capsule() -> Capsule {
    Capsule {
        goal: "Build memory for a local agent".into(),
        summary: "The local memory API works; device evaluation is next.".into(),
        constraints: vec!["Never put secrets into stored memory".into()],
        decisions: vec!["Use Rust + redb; keep checkpoint state durable".into()],
        open_tasks: vec!["Evaluate recall with a real local model".into()],
        next_action: "Test preference recall after a model context reset".into(),
    }
}

struct ProcessGuard(Child);
impl ProcessGuard {
    fn stop(&mut self) -> Result<()> {
        self.0.kill()?;
        self.0.wait()?;
        Ok(())
    }
}
impl Drop for ProcessGuard {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

async fn start(dir: &Path, token: &str) -> Result<(Client, ProcessGuard, String)> {
    let reservation = tokio::net::TcpListener::bind("127.0.0.1:0").await?;
    let address = reservation.local_addr()?;
    drop(reservation);
    let log = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("server.log"))?;
    let child = Command::new(std::env::current_exe()?)
        .args(["serve", "--bind", &address.to_string()])
        .current_dir(dir)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(log)
        .spawn()?;
    let mut process = ProcessGuard(child);
    let client = Client::new(&format!("http://{address}"), Some(token.into()))?;
    let deadline = Instant::now() + Duration::from_secs(15);
    loop {
        if client.health().await.is_ok() {
            return Ok((client, process, format!("http://{address}")));
        }
        if process.0.try_wait()?.is_some() || Instant::now() >= deadline {
            bail!(
                "demo server did not become ready; log: {}",
                std::fs::read_to_string(dir.join("server.log"))?
            );
        }
        tokio::time::sleep(Duration::from_millis(25)).await;
    }
}

pub async fn demo() -> Result<()> {
    let dir = tempfile::tempdir()?;
    crate::init(dir.path(), crate::Profile::Local)?;
    let secrets = instantkv::auth::read_secrets(&dir.path().join(".instantkv/credentials.env"))?;
    let token = secrets["INSTANTKV_APP_TOKEN"].clone();
    let (client, mut process, _) = start(dir.path(), &token).await?;
    let saved = client
        .remember(
            "knowledge",
            &RememberRequest {
                key: Some("preferences/language".into()),
                memory: MemoryInput {
                    content: "Prefer Rust for local tools".into(),
                    topic: Some("preferences".into()),
                    tags: vec!["local".into()],
                    occurred_at_ms: Some(1_790_985_600_000),
                    metadata: serde_json::from_value(json!({"source":"synthetic demo"}))?,
                },
                ttl_seconds: None,
                if_revision: None,
            },
        )
        .await?;
    println!("01  REMEMBER  saved content, topic, tag, event time and metadata");
    client
        .put(
            "scratch",
            "working",
            b"{\"temporary\":true}".to_vec(),
            Some(1),
            None,
            false,
        )
        .await?;
    let mut context = Some(capsule());
    let request = CheckpointRequest {
        id: uuid::Uuid::new_v4().to_string(),
        agent_id: "demo-agent".into(),
        session_id: "build-1".into(),
        expected_latest_revision: None,
        capsule: context.clone().unwrap(),
        references: vec![MemoryReference {
            namespace: "knowledge".into(),
            key: "preferences/language".into(),
            revision: saved.revision,
        }],
    };
    let receipt = client.checkpoint("checkpoints", &request).await?;
    let locator_path = dir.path().join("session-locator.json");
    std::fs::write(&locator_path, serde_json::to_vec(&receipt)?)?;
    println!("02  SAVE      committed checkpoint + latest pointer atomically");
    context.take();
    assert!(context.is_none());
    println!("03  COMPACT   cleared simulated agent context; locator stays outside it");
    process.stop()?;
    drop(client);
    let (client, mut process, _) = start(dir.path(), &token).await?;
    println!("04  RESTART   reopened the same database with an empty scratch cache");
    let receipt: instantkv_core::model::CheckpointReceipt =
        serde_json::from_slice(&std::fs::read(locator_path)?)?;
    let restored = client.restore("checkpoints", &receipt.id, 32768).await?;
    assert_eq!(restored.capsule, request.capsule);
    let recalled = client
        .recall(
            "knowledge",
            &MemoryQuery {
                topic: Some("preferences".into()),
                tag: Some("local".into()),
                query: Some("Rust local".into()),
                since_ms: Some(1_790_985_600_000),
                until_ms: Some(1_790_985_600_000),
                ..Default::default()
            },
        )
        .await?;
    assert_eq!(
        serde_json::to_value(&recalled.items[0])?,
        serde_json::to_value(&saved)?
    );
    assert!(client.get("scratch", "working").await.is_err());
    assert_eq!(
        client
            .restore_latest("checkpoints", "demo-agent", "build-1", 32768)
            .await?
            .checkpoint_id,
        receipt.id
    );
    println!("05  RESTORE   recovered goal, constraints, decisions, sources, next action");
    println!("06  RECALL    topic + tag + time + keywords recovered the exact memory");
    let ranked = client
        .search(
            "knowledge",
            &SearchQuery {
                query: "preferred language for local tooling".into(),
                ..Default::default()
            },
        )
        .await?;
    assert_eq!(ranked.items[0].hit.key, saved.key);
    assert!(!ranked.truncated);
    println!("    SEARCH    BM25 ranked the saved preference after restart; no model call");
    let browsed = client.recall("knowledge", &MemoryQuery::default()).await?;
    assert_eq!(browsed.items.len(), 1);
    println!("07  BROWSE    bounded page lists durable memories; scratch is empty");
    client
        .forget("knowledge", &saved.key, Some(saved.revision))
        .await?;
    assert!(
        client
            .recall("knowledge", &MemoryQuery::default())
            .await?
            .items
            .is_empty()
    );
    assert!(
        client
            .memory_get("knowledge", &saved.key)
            .await
            .unwrap_err()
            .to_string()
            .contains("404")
    );
    println!("08  FORGET    revision-checked deletion removes the record and indexes");
    println!("\nNext action: {}", restored.capsule.next_action);
    println!("PASS: five memory tools + checkpoint handoff + restart via real HTTP");
    process.stop()?;
    Ok(())
}

pub async fn swarm_demo() -> Result<()> {
    let dir = tempfile::tempdir()?;
    crate::init(dir.path(), crate::Profile::Swarm)?;
    let secrets = instantkv::auth::read_secrets(&dir.path().join(".instantkv/credentials.env"))?;
    let token = &secrets["INSTANTKV_APP_TOKEN"];
    let (operator, mut process, url) = start(dir.path(), token).await?;
    let alpha = Client::new(&url, Some(secrets["INSTANTKV_ALPHA_TOKEN"].clone()))?;
    let beta = Client::new(&url, Some(secrets["INSTANTKV_BETA_TOKEN"].clone()))?;
    let input = |key: &str, content: &str, topic: &str| RememberRequest {
        key: Some(key.into()),
        memory: MemoryInput {
            content: content.into(),
            topic: Some(topic.into()),
            tags: vec!["local".into()],
            ..Default::default()
        },
        ttl_seconds: None,
        if_revision: None,
    };
    let shared = operator
        .remember(
            "shared",
            &input("project/storage", "Use Rust + redb", "project"),
        )
        .await?;
    let baseline = serde_json::to_vec(&shared.memory)?;
    assert_eq!(alpha.get("shared", "project/storage").await?.0, baseline);
    assert_eq!(beta.get("shared", "project/storage").await?.0, baseline);
    assert_eq!(
        alpha
            .recall(
                "shared",
                &MemoryQuery {
                    topic: Some("project".into()),
                    ..Default::default()
                }
            )
            .await?
            .items
            .len(),
        1
    );
    println!("01  SHARED    both agents recall structured project memory");
    let own = alpha
        .remember(
            "alpha",
            &input("run/findings", "Alpha verified the memory API", "findings"),
        )
        .await?;
    let alpha_note = serde_json::to_vec(&own.memory)?;
    beta.remember(
        "beta",
        &input("run/findings", "Beta checked local deployment", "findings"),
    )
    .await?;
    assert!(
        alpha
            .put(
                "shared",
                "project/storage",
                b"{}".to_vec(),
                None,
                None,
                false
            )
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    assert!(
        alpha
            .get("beta", "run/findings")
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    assert!(
        beta.get("alpha", "run/findings")
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    println!(
        "02  PRIVATE   agents write independently; cross-agent reads and shared writes return 403"
    );
    let mut context = Some(capsule());
    let request = CheckpointRequest {
        id: "alpha-handoff".into(),
        agent_id: "alpha".into(),
        session_id: "run-1".into(),
        expected_latest_revision: None,
        capsule: context.clone().unwrap(),
        references: vec![
            MemoryReference {
                namespace: "shared".into(),
                key: "project/storage".into(),
                revision: shared.revision,
            },
            MemoryReference {
                namespace: "alpha".into(),
                key: "run/findings".into(),
                revision: own.revision,
            },
        ],
    };
    let receipt = alpha.checkpoint("alpha_checkpoints", &request).await?;
    std::fs::write(
        dir.path().join("alpha-locator.json"),
        serde_json::to_vec(&receipt)?,
    )?;
    context.take();
    assert!(context.is_none());
    assert!(
        beta.restore("alpha_checkpoints", &receipt.id, 32768)
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    println!(
        "03  HANDOFF   saved private capsule; cleared simulated context; locator lives outside it"
    );
    process.stop()?;
    let (_, mut process, url) = start(dir.path(), token).await?;
    let alpha = Client::new(&url, Some(secrets["INSTANTKV_ALPHA_TOKEN"].clone()))?;
    let receipt: instantkv_core::model::CheckpointReceipt =
        serde_json::from_slice(&std::fs::read(dir.path().join("alpha-locator.json"))?)?;
    let restored = alpha
        .restore("alpha_checkpoints", &receipt.id, 32768)
        .await?;
    assert_eq!(restored.capsule, request.capsule);
    assert!(restored.references.iter().all(|reference| matches!(
        reference.status,
        instantkv_core::model::ReferenceStatus::Available
    )));
    assert_eq!(alpha.get("alpha", "run/findings").await?.0, alpha_note);
    assert_eq!(alpha.get("shared", "project/storage").await?.0, baseline);
    println!(
        "04  RESTORE   after real server restart, Alpha restores its capsule and both knowledge sources"
    );
    let private = alpha
        .recall(
            "alpha",
            &MemoryQuery {
                topic: Some("findings".into()),
                ..Default::default()
            },
        )
        .await?;
    assert_eq!(private.items.len(), 1);
    alpha.forget("alpha", &own.key, Some(own.revision)).await?;
    assert!(
        alpha
            .recall("alpha", &MemoryQuery::default())
            .await?
            .items
            .is_empty()
    );
    assert_eq!(
        alpha
            .recall("shared", &MemoryQuery::default())
            .await?
            .items
            .len(),
        1
    );
    println!("05  FORGET    Alpha deletes private memory; shared facts remain");
    println!("PASS: structured shared memory + isolated agents + durable handoff over real HTTP");
    process.stop()?;
    Ok(())
}

#[allow(clippy::too_many_arguments)]
pub async fn bench(
    client: Client,
    namespace: &str,
    operation: &str,
    requests: usize,
    concurrency: usize,
    value_bytes: usize,
    output: Option<&Path>,
) -> Result<()> {
    if requests == 0
        || requests > 1_000_000
        || concurrency == 0
        || concurrency > 1024
        || !(2..=1048576).contains(&value_bytes)
    {
        bail!("requests must be 1..1000000, concurrency 1..1024, value-bytes 2..1048576");
    }
    let run_id = uuid::Uuid::new_v4().simple().to_string();
    let value = serde_json::to_vec(&"x".repeat(value_bytes - 2))?;
    let mut keys = Vec::new();
    if matches!(operation, "get" | "put") {
        for index in 0..concurrency {
            let key = format!("bench/{run_id}/{index}");
            client
                .put(namespace, &key, value.clone(), None, None, false)
                .await?;
            keys.push(key);
        }
    }
    let mut checkpoint_ids = Vec::new();
    if operation == "restore" {
        for index in 0..concurrency {
            let id = format!("{run_id}-{index}");
            client
                .checkpoint(
                    namespace,
                    &CheckpointRequest {
                        id: id.clone(),
                        agent_id: "benchmark".into(),
                        session_id: id.clone(),
                        expected_latest_revision: None,
                        capsule: capsule(),
                        references: vec![],
                    },
                )
                .await?;
            checkpoint_ids.push(id);
        }
    }
    // Warm up connections and storage; setup and warmup are excluded from timings.
    for index in 0..concurrency {
        match operation {
            "get" => {
                client.get(namespace, &keys[index]).await?;
            }
            "restore" => {
                client
                    .restore(namespace, &checkpoint_ids[index], 32768)
                    .await?;
            }
            _ => {}
        }
    }
    let start = Instant::now();
    let mut tasks = JoinSet::new();
    for worker in 0..concurrency.min(requests) {
        let client = client.clone();
        let namespace = namespace.to_owned();
        let operation = operation.to_owned();
        let value = value.clone();
        let key = keys.get(worker).cloned();
        let checkpoint_id = checkpoint_ids.get(worker).cloned();
        let run_id = run_id.clone();
        tasks.spawn(async move {
            let mut timings = Vec::new();
            let mut errors = 0;
            for index in (worker..requests).step_by(concurrency) {
                let start = Instant::now();
                let result = match operation.as_str() {
                    "get" => client
                        .get(&namespace, key.as_deref().unwrap())
                        .await
                        .map(|_| ()),
                    "put" => client
                        .put(
                            &namespace,
                            key.as_deref().unwrap(),
                            value.clone(),
                            None,
                            None,
                            false,
                        )
                        .await
                        .map(|_| ()),
                    "restore" => client
                        .restore(&namespace, checkpoint_id.as_deref().unwrap(), 32768)
                        .await
                        .map(|_| ()),
                    "checkpoint" => {
                        let id = format!("{run_id}-{index}");
                        client
                            .checkpoint(
                                &namespace,
                                &CheckpointRequest {
                                    id: id.clone(),
                                    agent_id: "benchmark".into(),
                                    session_id: id,
                                    expected_latest_revision: None,
                                    capsule: capsule(),
                                    references: vec![],
                                },
                            )
                            .await
                            .map(|_| ())
                    }
                    _ => unreachable!(),
                };
                if result.is_err() {
                    errors += 1;
                }
                timings.push(start.elapsed().as_secs_f64() * 1000.0);
            }
            (timings, errors)
        });
    }
    let mut timings = Vec::with_capacity(requests);
    let mut errors = 0;
    while let Some(result) = tasks.join_next().await {
        let (worker, failures) = result?;
        timings.extend(worker);
        errors += failures;
    }
    let elapsed = start.elapsed().as_secs_f64();
    timings.sort_by(f64::total_cmp);
    let percentile =
        |fraction: f64| timings[((timings.len() - 1) as f64 * fraction).ceil() as usize];
    let report = json!({"schema_version":1, "operation":operation,"namespace":namespace,"requests":requests,"concurrency":concurrency,"value_bytes":if matches!(operation,"get"|"put"){Some(value_bytes)}else{None},"elapsed_seconds":elapsed,"successful_requests":requests-errors,"errors":errors,"successful_requests_per_second":(requests-errors) as f64/elapsed,"latency_ms":{"p50":percentile(0.50),"p95":percentile(0.95),"p99":percentile(0.99)},"transport":"HTTP/1.1 keep-alive, closed-loop client; no pipelining","durability":"server configuration; durable namespaces use immediate commits","client_version":env!("CARGO_PKG_VERSION")});
    let report_text = serde_json::to_string_pretty(&report)?;
    println!("{report_text}");
    if let Some(path) = output {
        std::fs::write(path, format!("{report_text}\n"))?;
    }
    for key in keys {
        client.delete(namespace, &key, None).await?;
    }
    if errors > 0 {
        bail!("benchmark had {errors} failed requests; no success claim");
    }
    Ok(())
}
