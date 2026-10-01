use anyhow::{Context, Result, bail};
use instantkv::client::Client;
use instantkv_core::model::{Capsule, CheckpointRequest, MemoryReference};
use serde_json::json;
use std::{
    path::Path,
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};
use tokio::task::JoinSet;

fn capsule() -> Capsule {
    Capsule {
        goal: "Ship an agent-memory KV service".into(),
        summary: "The storage decision is saved; the HTTP layer is next.".into(),
        constraints: vec!["Never put secrets into stored memory".into()],
        decisions: vec!["Use Rust + redb; keep checkpoint state durable".into()],
        open_tasks: vec!["Connect the MCP adapter".into()],
        next_action: "Implement memory_get and memory_checkpoint tools".into(),
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
    crate::init(dir.path(), crate::Profile::Agent)?;
    let secrets = instantkv::auth::read_secrets(&dir.path().join(".instantkv/credentials.env"))?;
    let token = secrets["INSTANTKV_APP_TOKEN"].clone();
    let (client, mut process, _) = start(dir.path(), &token).await?;
    let decision =
        br#"{"kind":"decision","content":"Use Rust + redb","source":"docs/architecture.md"}"#
            .to_vec();
    let saved = client
        .put(
            "knowledge",
            "project/storage",
            decision.clone(),
            None,
            None,
            true,
        )
        .await?;
    println!("01  PARK      saved project/storage in durable knowledge");
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
            key: "project/storage".into(),
            revision: saved["revision"].as_u64().context("missing revision")?,
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
    assert_eq!(
        client.get("knowledge", "project/storage").await?.0,
        decision
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
    println!("06  RECALL    durable knowledge survived; disposable scratch did not");
    println!("\nNext action: {}", restored.capsule.next_action);
    println!("PASS: compaction handoff and database restart via real HTTP requests");
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
    let baseline = br#"{"content":"Use Rust + redb","source":"docs/architecture.md"}"#.to_vec();
    let mother = operator
        .put(
            "mother",
            "project/storage",
            baseline.clone(),
            None,
            None,
            true,
        )
        .await?;
    assert_eq!(alpha.get("mother", "project/storage").await?.0, baseline);
    assert_eq!(beta.get("mother", "project/storage").await?.0, baseline);
    println!("01  MOTHER    both cloud agents recall the same shared baseline");
    let alpha_note = br#"{"content":"Alpha verified the HTTP contract"}"#.to_vec();
    let own = alpha
        .put(
            "alpha",
            "run/findings",
            alpha_note.clone(),
            None,
            None,
            true,
        )
        .await?;
    beta.put(
        "beta",
        "run/findings",
        b"{\"content\":\"Beta checked deployment\"}".to_vec(),
        None,
        None,
        true,
    )
    .await?;
    assert!(
        alpha
            .put(
                "mother",
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
        "02  PRIVATE   agents write independently; cross-agent reads and mother writes return 403"
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
                namespace: "mother".into(),
                key: "project/storage".into(),
                revision: mother["revision"]
                    .as_u64()
                    .context("missing mother revision")?,
            },
            MemoryReference {
                namespace: "alpha".into(),
                key: "run/findings".into(),
                revision: own["revision"]
                    .as_u64()
                    .context("missing private revision")?,
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
    assert_eq!(alpha.get("mother", "project/storage").await?.0, baseline);
    println!(
        "04  RESTORE   after real server restart, Alpha restores its capsule and both knowledge sources"
    );
    println!("PASS: shared mother + isolated agents + durable handoff over real HTTP");
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
