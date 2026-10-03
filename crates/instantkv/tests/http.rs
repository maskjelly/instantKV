use instantkv::{
    auth::Auth,
    client::Client,
    server::{App, router},
};
use instantkv_core::{
    Engine,
    config::Config,
    model::{Capsule, CheckpointRequest},
};
use std::{collections::HashMap, sync::Arc};

const APP_TOKEN: &str = "test-app-token-00000000000000000000000000000000000000";
const READER_TOKEN: &str = "test-reader-token-00000000000000000000000000000000000";
const ALPHA_TOKEN: &str = "test-alpha-token-000000000000000000000000000000000000";
const BETA_TOKEN: &str = "test-beta-token-0000000000000000000000000000000000000";

struct Harness {
    _dir: tempfile::TempDir,
    client: Client,
    base: String,
    task: tokio::task::JoinHandle<()>,
}
impl Drop for Harness {
    fn drop(&mut self) {
        self.task.abort();
    }
}

async fn start(mut config: Config) -> Harness {
    let dir = tempfile::tempdir().unwrap();
    config.storage.data_dir = dir.path().into();
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    config.server.bind = listener.local_addr().unwrap();
    let base = format!("http://{}", config.server.bind);
    let secrets = HashMap::from([
        ("INSTANTKV_APP_TOKEN".into(), APP_TOKEN.into()),
        ("INSTANTKV_READER_TOKEN".into(), READER_TOKEN.into()),
        ("INSTANTKV_ALPHA_TOKEN".into(), ALPHA_TOKEN.into()),
        ("INSTANTKV_BETA_TOKEN".into(), BETA_TOKEN.into()),
    ]);
    let auth = Auth::load(&config, &secrets).unwrap();
    let engine = Arc::new(Engine::open(config).unwrap());
    let app = App::new(engine, auth);
    let task = tokio::spawn(async move {
        axum::serve(listener, router(app)).await.unwrap();
    });
    Harness {
        client: Client::new(&base, Some(APP_TOKEN.into())).unwrap(),
        base,
        _dir: dir,
        task,
    }
}

fn config() -> Config {
    Config::parse(include_str!("../../../config/instantkv.example.toml")).unwrap()
}

#[tokio::test]
async fn ranked_search_requires_both_grants_and_preserves_exact_memory_routes() {
    use instantkv_core::{
        config::Operation,
        memory::{MemoryInput, RememberRequest},
        search::SearchQuery,
    };
    let server = start(config()).await;
    server
        .client
        .remember(
            "knowledge",
            &RememberRequest {
                key: Some("search".into()),
                memory: MemoryInput {
                    content: "Antibodies bind immune cells".into(),
                    ..Default::default()
                },
                ttl_seconds: None,
                if_revision: None,
            },
        )
        .await
        .unwrap();
    assert_eq!(
        server
            .client
            .memory_get("knowledge", "search")
            .await
            .unwrap()
            .key,
        "search"
    );
    let reader = Client::new(&server.base, Some(READER_TOKEN.into())).unwrap();
    let q = SearchQuery {
        query: "How does an antibody bind?".into(),
        ..Default::default()
    };
    let page = reader.search("knowledge", &q).await.unwrap();
    assert_eq!(page.items[0].hit.key, "search");
    assert!(page.items[0].score > 0.0);
    assert!(
        reader
            .search("scratch", &q)
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    for operations in [vec![Operation::List], vec![Operation::Get]] {
        let mut c = config();
        c.auth
            .principals
            .iter_mut()
            .find(|p| p.name == "reader")
            .unwrap()
            .operations = operations;
        let restricted = start(c).await;
        let reader = Client::new(&restricted.base, Some(READER_TOKEN.into())).unwrap();
        assert!(
            reader
                .search("knowledge", &q)
                .await
                .unwrap_err()
                .to_string()
                .contains("403")
        );
    }
}

#[tokio::test]
async fn memory_api_creates_filters_updates_and_forgets_with_revision_conditions() {
    use instantkv_core::memory::{MemoryInput, MemoryQuery, RememberRequest};
    let server = start(config()).await;
    let request = RememberRequest {
        key: Some("prefs/rust".into()),
        memory: MemoryInput {
            content: "Prefer Rust for local tools".into(),
            topic: Some("Preferences".into()),
            tags: vec!["Local".into()],
            metadata: serde_json::from_value(serde_json::json!({"source":"user"})).unwrap(),
            occurred_at_ms: Some(1234),
        },
        ttl_seconds: None,
        if_revision: None,
    };
    let first = server.client.remember("knowledge", &request).await.unwrap();
    assert_eq!(first.key, "prefs/rust");
    assert!(
        server
            .client
            .remember("knowledge", &request)
            .await
            .unwrap_err()
            .to_string()
            .contains("409")
    );
    let reader = Client::new(&server.base, Some(READER_TOKEN.into())).unwrap();
    let query = MemoryQuery {
        topic: Some("preferences".into()),
        tag: Some("local".into()),
        query: Some("rust TOOLS".into()),
        since_ms: Some(1234),
        until_ms: Some(1234),
        ..Default::default()
    };
    let page = reader.recall("knowledge", &query).await.unwrap();
    assert_eq!(page.items.len(), 1);
    assert_eq!(page.items[0].memory.metadata["source"], "user");
    assert_eq!(
        reader
            .memory_get("knowledge", "prefs/rust")
            .await
            .unwrap()
            .revision,
        first.revision
    );
    let mut update = request.clone();
    update.if_revision = Some(first.revision);
    update.memory.topic = Some("work".into());
    let updated = server.client.remember("knowledge", &update).await.unwrap();
    assert!(
        reader
            .recall("knowledge", &query)
            .await
            .unwrap()
            .items
            .is_empty()
    );
    assert!(
        reader
            .remember("knowledge", &update)
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    assert!(
        reader
            .forget("knowledge", &first.key, None)
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    assert!(
        server
            .client
            .forget("knowledge", &first.key, Some(first.revision))
            .await
            .unwrap_err()
            .to_string()
            .contains("409")
    );
    server
        .client
        .forget("knowledge", &first.key, Some(updated.revision))
        .await
        .unwrap();
    assert!(
        reader
            .recall("knowledge", &MemoryQuery::default())
            .await
            .unwrap()
            .items
            .is_empty()
    );
    let mut generated = request;
    generated.key = None;
    let saved = server
        .client
        .remember("knowledge", &generated)
        .await
        .unwrap();
    assert!(saved.key.starts_with("memories/"));
}

#[tokio::test]
async fn memory_queries_need_both_list_and_get_and_never_cross_scopes() {
    use instantkv_core::{config::Operation, memory::MemoryQuery};
    let mut conf = config();
    conf.auth
        .principals
        .iter_mut()
        .find(|p| p.name == "reader")
        .unwrap()
        .operations = vec![Operation::List];
    let server = start(conf).await;
    let reader = Client::new(&server.base, Some(READER_TOKEN.into())).unwrap();
    assert!(reader.list("knowledge", "", 10, None).await.is_ok());
    assert!(
        reader
            .recall("knowledge", &MemoryQuery::default())
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    let anonymous = Client::new(&server.base, None).unwrap();
    assert!(
        anonymous
            .recall("knowledge", &MemoryQuery::default())
            .await
            .unwrap_err()
            .to_string()
            .contains("401")
    );
    let server = start(Config::parse(include_str!("../../../config/swarm.toml")).unwrap()).await;
    let alpha = Client::new(&server.base, Some(ALPHA_TOKEN.into())).unwrap();
    assert!(
        alpha
            .recall("beta", &MemoryQuery::default())
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    assert!(
        alpha
            .recall("shared", &MemoryQuery::default())
            .await
            .is_ok()
    );
}

#[tokio::test]
async fn swarm_isolation_and_restore_reference_grants_are_enforced() {
    use instantkv_core::model::{MemoryReference, ReferenceStatus};
    let server = start(Config::parse(include_str!("../../../config/swarm.toml")).unwrap()).await;
    let alpha = Client::new(&server.base, Some(ALPHA_TOKEN.into())).unwrap();
    let beta = Client::new(&server.base, Some(BETA_TOKEN.into())).unwrap();
    for namespace in ["shared", "alpha", "beta"] {
        server
            .client
            .put(namespace, "fact", b"1".to_vec(), None, None, true)
            .await
            .unwrap();
    }
    assert_eq!(alpha.get("shared", "fact").await.unwrap().0, b"1");
    assert_eq!(
        alpha
            .list("shared", "", 100, None)
            .await
            .unwrap()
            .items
            .len(),
        1
    );
    for result in [
        alpha.get("beta", "fact").await.map(|_| ()),
        alpha
            .put("shared", "fact", b"2".to_vec(), None, None, false)
            .await
            .map(|_| ()),
        alpha.delete("shared", "fact", None).await,
        alpha.stats("shared").await.map(|_| ()),
        alpha.list("beta", "", 100, None).await.map(|_| ()),
        beta.get("alpha", "fact").await.map(|_| ()),
    ] {
        assert!(result.unwrap_err().to_string().contains("403"));
    }
    let own = alpha
        .put("alpha", "fact", b"2".to_vec(), None, Some(1), false)
        .await
        .unwrap();
    assert_eq!(own["revision"], 2);
    let request = CheckpointRequest {
        id: "alpha-cp".into(),
        agent_id: "alpha".into(),
        session_id: "run".into(),
        expected_latest_revision: None,
        capsule: Capsule {
            goal: "Continue".into(),
            summary: "Scoped recall".into(),
            constraints: vec![],
            decisions: vec![],
            open_tasks: vec![],
            next_action: "Recall".into(),
        },
        references: ["shared", "alpha", "beta"]
            .into_iter()
            .map(|namespace| MemoryReference {
                namespace: namespace.into(),
                key: "fact".into(),
                revision: if namespace == "alpha" { 2 } else { 1 },
            })
            .collect(),
    };
    // Agents cannot save references outside their readable scopes. An operator
    // can create a broader capsule, but agent restore must still redact status.
    assert!(
        alpha
            .checkpoint("alpha_checkpoints", &request)
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    server
        .client
        .checkpoint("alpha_checkpoints", &request)
        .await
        .unwrap();
    let restored = alpha
        .restore("alpha_checkpoints", "alpha-cp", 32768)
        .await
        .unwrap();
    assert!(matches!(
        restored.references[0].status,
        ReferenceStatus::Available
    ));
    assert!(matches!(
        restored.references[1].status,
        ReferenceStatus::Available
    ));
    assert!(matches!(
        restored.references[2].status,
        ReferenceStatus::Forbidden
    ));
    assert!(
        beta.restore("alpha_checkpoints", "alpha-cp", 32768)
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    alpha.delete("alpha", "fact", Some(2)).await.unwrap();
}

#[tokio::test]
async fn http_handles_slashes_unicode_and_conditional_writes() {
    let server = start(config()).await;
    let key = "project/architecture/λ?percent%";
    let saved = server
        .client
        .put(
            "knowledge",
            key,
            b"{\"value\":42}".to_vec(),
            None,
            None,
            true,
        )
        .await
        .unwrap();
    let (bytes, revision) = server.client.get("knowledge", key).await.unwrap();
    assert_eq!(bytes, b"{\"value\":42}");
    assert_eq!(revision, saved["revision"]);
    assert!(
        server
            .client
            .put("knowledge", key, b"1".to_vec(), None, None, true)
            .await
            .is_err()
    );
    assert!(
        server
            .client
            .put(
                "knowledge",
                key,
                b"1".to_vec(),
                None,
                Some(revision + 1),
                false
            )
            .await
            .is_err()
    );
    let page = server
        .client
        .list("knowledge", "project/", 1, None)
        .await
        .unwrap();
    assert_eq!(page.items[0].key, key);
    let last = server
        .client
        .list("knowledge", "project/", 1, page.next_cursor.as_deref())
        .await
        .unwrap();
    assert!(last.items.is_empty());
    server
        .client
        .delete("knowledge", key, Some(revision))
        .await
        .unwrap();
    assert!(server.client.get("knowledge", key).await.is_err());
}

#[tokio::test]
async fn credentials_and_namespace_grants_are_enforced() {
    let server = start(config()).await;
    server
        .client
        .put("knowledge", "key", b"1".to_vec(), None, None, false)
        .await
        .unwrap();
    let anonymous = Client::new(&server.base, None).unwrap();
    assert!(
        anonymous
            .get("knowledge", "key")
            .await
            .unwrap_err()
            .to_string()
            .contains("401")
    );
    let reader = Client::new(&server.base, Some(READER_TOKEN.into())).unwrap();
    assert!(reader.get("knowledge", "key").await.is_ok());
    // Key suffixes must not be confused with control endpoints by the auth gate.
    server
        .client
        .put(
            "knowledge",
            "project/stats",
            b"1".to_vec(),
            None,
            None,
            false,
        )
        .await
        .unwrap();
    assert!(reader.get("knowledge", "project/stats").await.is_ok());
    assert!(reader.list("knowledge", "", 10, None).await.is_ok());
    assert!(
        reader
            .put("knowledge", "key", b"2".to_vec(), None, None, false)
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    assert!(
        reader
            .get("scratch", "key")
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    assert!(
        reader
            .stats("knowledge")
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
}

#[tokio::test]
async fn invalid_ttl_json_and_bodies_are_rejected() {
    let mut cfg = config();
    cfg.server.max_request_body_bytes = 1024;
    for ns in &mut cfg.namespaces {
        ns.admission.max_value_bytes = 1024;
    }
    let server = start(cfg).await;
    assert!(
        server
            .client
            .put("knowledge", "key", b"not-json".to_vec(), None, None, false)
            .await
            .is_err()
    );
    assert!(
        server
            .client
            .put("scratch", "key", b"1".to_vec(), Some(0), None, false)
            .await
            .is_err()
    );
    assert!(
        server
            .client
            .put("scratch", "key", b"1".to_vec(), Some(86401), None, false)
            .await
            .is_err()
    );
    assert!(
        server
            .client
            .put("knowledge", "key", vec![b' '; 1025], None, None, false)
            .await
            .unwrap_err()
            .to_string()
            .contains("413")
    );
    assert_eq!(server.client.stats("knowledge").await.unwrap().entries, 0);
}

#[tokio::test]
async fn checkpoint_and_restore_preserve_required_context() {
    let server = start(config()).await;
    let request = CheckpointRequest {
        id: "cp-http".into(),
        agent_id: "agent".into(),
        session_id: "session".into(),
        expected_latest_revision: None,
        capsule: Capsule {
            goal: "Ship".into(),
            summary: "Decision saved".into(),
            constraints: vec!["No keys in logs".into()],
            decisions: vec![],
            open_tasks: vec!["Benchmark".into()],
            next_action: "Measure restore".into(),
        },
        references: vec![],
    };
    let receipt = server
        .client
        .checkpoint("checkpoints", &request)
        .await
        .unwrap();
    let restored = server
        .client
        .restore_latest("checkpoints", "agent", "session", 32768)
        .await
        .unwrap();
    assert_eq!(restored.capsule, request.capsule);
    assert_eq!(restored.latest_revision, receipt.latest_revision);
    assert!(
        server
            .client
            .delete_checkpoint("checkpoints", "cp-http")
            .await
            .unwrap_err()
            .to_string()
            .contains("409")
    );
    let mut next = request.clone();
    next.id = "cp-http-next".into();
    next.expected_latest_revision = Some(receipt.latest_revision);
    server
        .client
        .checkpoint("checkpoints", &next)
        .await
        .unwrap();
    let reader = Client::new(&server.base, Some(READER_TOKEN.into())).unwrap();
    assert!(
        reader
            .delete_checkpoint("checkpoints", "cp-http")
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
    server
        .client
        .delete_checkpoint("checkpoints", "cp-http")
        .await
        .unwrap();
    assert!(
        server
            .client
            .restore("checkpoints", "cp-http", 32768)
            .await
            .unwrap_err()
            .to_string()
            .contains("404")
    );
    assert!(
        server
            .client
            .put(
                "checkpoints",
                "__latest/agent/session",
                b"1".to_vec(),
                None,
                None,
                false
            )
            .await
            .is_err()
    );
    assert!(
        server
            .client
            .restore("checkpoints", "cp-http", 100)
            .await
            .is_err()
    );
    let reader = Client::new(&server.base, Some(READER_TOKEN.into())).unwrap();
    assert!(
        reader
            .restore("checkpoints", "cp-http", 32768)
            .await
            .unwrap_err()
            .to_string()
            .contains("403")
    );
}

#[test]
fn server_refuses_missing_short_and_duplicate_secrets() {
    let cfg = config();
    assert!(Auth::load(&cfg, &HashMap::new()).is_err());
    assert!(
        Auth::load(
            &cfg,
            &HashMap::from([("INSTANTKV_APP_TOKEN".into(), "short".into())])
        )
        .is_err()
    );
    assert!(
        Auth::load(
            &cfg,
            &HashMap::from([
                ("INSTANTKV_APP_TOKEN".into(), APP_TOKEN.into()),
                ("INSTANTKV_READER_TOKEN".into(), APP_TOKEN.into())
            ])
        )
        .is_err()
    );
}

#[tokio::test]
async fn cli_accepts_a_checkpoint_from_stdin() {
    use tokio::io::AsyncWriteExt;
    let server = start(config()).await;
    let request = serde_json::json!({"id":"stdin-cp","agent_id":"cli-agent","session_id":"cli-session","capsule":{"goal":"Ship","summary":"Input comes from the host","next_action":"Continue"},"references":[]});
    let mut child = tokio::process::Command::new(env!("CARGO_BIN_EXE_instantkv"))
        .args(["--url", &server.base, "checkpoint"])
        .env("INSTANTKV_TOKEN", APP_TOKEN)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .kill_on_drop(true)
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    input
        .write_all(request.to_string().as_bytes())
        .await
        .unwrap();
    input.shutdown().await.unwrap();
    drop(input);
    let output = child.wait_with_output().await.unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let receipt: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(receipt["id"], "stdin-cp");
    assert_eq!(
        server
            .client
            .restore("checkpoints", "stdin-cp", 32768)
            .await
            .unwrap()
            .capsule
            .next_action,
        "Continue"
    );
}

#[tokio::test]
async fn mcp_stdio_tools_save_and_restore_through_authenticated_http() {
    use serde_json::{Value, json};
    use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
    let server = start(config()).await;
    let mut child = tokio::process::Command::new(env!("CARGO_BIN_EXE_instantkv"))
        .args(["--url", &server.base, "mcp"])
        .env("INSTANTKV_TOKEN", APP_TOKEN)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .kill_on_drop(true)
        .spawn()
        .unwrap();
    let mut input = child.stdin.take().unwrap();
    let mut output = BufReader::new(child.stdout.take().unwrap()).lines();
    async fn call(
        input: &mut tokio::process::ChildStdin,
        output: &mut tokio::io::Lines<BufReader<tokio::process::ChildStdout>>,
        value: Value,
    ) -> Value {
        input
            .write_all(format!("{value}\n").as_bytes())
            .await
            .unwrap();
        loop {
            let line = tokio::time::timeout(std::time::Duration::from_secs(10), output.next_line())
                .await
                .unwrap()
                .unwrap()
                .unwrap();
            let response: Value = serde_json::from_str(&line).unwrap();
            if response["id"] == value["id"] {
                assert!(response.get("error").is_none(), "{response}");
                return response["result"].clone();
            }
        }
    }
    let init = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"instantkv-test","version":"1"}}})).await;
    assert_eq!(init["serverInfo"]["name"], "instantkv");
    input
        .write_all(b"{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\"}\n")
        .await
        .unwrap();
    let tools = call(
        &mut input,
        &mut output,
        json!({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}),
    )
    .await;
    assert_eq!(tools["tools"].as_array().unwrap().len(), 12);
    for name in ["remember", "recall", "search", "browse", "forget"] {
        assert!(
            tools["tools"]
                .as_array()
                .unwrap()
                .iter()
                .any(|tool| tool["name"] == name)
        );
    }
    let saved = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"memory_put","arguments":{"key":"mcp/decision","value":{"content":"Keep memory durable"}}}})).await;
    assert_eq!(saved["isError"], false);
    let got = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"memory_get","arguments":{"key":"mcp/decision"}}})).await;
    assert_eq!(
        got["structuredContent"]["value"]["content"],
        "Keep memory durable"
    );
    let checkpoint = json!({"id":"mcp-checkpoint","agent_id":"mcp-agent","session_id":"mcp-session","expected_latest_revision":null,"capsule":{"goal":"Ship","summary":"Decision saved","constraints":["No secrets"],"decisions":[],"open_tasks":[],"next_action":"Continue"},"references":[]});
    let saved = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"memory_checkpoint","arguments":{"checkpoint":checkpoint}}})).await;
    assert_eq!(saved["isError"], false);
    let restored = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"memory_restore","arguments":{"agent_id":"mcp-agent","session_id":"mcp-session"}}})).await;
    assert_eq!(
        restored["structuredContent"]["capsule"]["constraints"][0],
        "No secrets"
    );
    let missing = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"memory_get","arguments":{"key":"missing"}}})).await;
    assert_eq!(missing["isError"], true);
    let memory = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"remember","arguments":{"key":"preferences/editor","content":"Use Neovim locally","topic":"Preferences","tags":["local"],"metadata":{"source":"user"},"occurred_at_ms":1234}}})).await;
    assert_eq!(memory["isError"], false);
    let recall = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"recall","arguments":{"topic":"preferences","tag":"local","query":"neovim","since_ms":1234,"until_ms":1234}}})).await;
    assert_eq!(
        recall["structuredContent"]["items"][0]["memory"]["content"],
        "Use Neovim locally"
    );
    let browse = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"browse","arguments":{}}})).await;
    let ranked = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"search","arguments":{"query":"Which editor should I use locally?"}}})).await;
    assert_eq!(ranked["isError"], false);
    assert_eq!(
        ranked["structuredContent"]["items"][0]["key"],
        "preferences/editor"
    );
    assert!(
        ranked["structuredContent"]["items"][0]["score"]
            .as_f64()
            .unwrap()
            > 0.0
    );
    assert_eq!(
        browse["structuredContent"]["items"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    let forgotten = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"forget","arguments":{"key":"preferences/editor"}}})).await;
    assert_eq!(forgotten["structuredContent"]["forgotten"], true);
    let browse = call(&mut input, &mut output, json!({"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"browse","arguments":{}}})).await;
    assert!(
        browse["structuredContent"]["items"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    child.kill().await.unwrap();
    child.wait().await.unwrap();
}

#[tokio::test]
async fn cli_memory_commands_and_generated_schemas_match_the_live_api() {
    use serde_json::Value;
    let server = start(config()).await;
    async fn cli(server: &Harness, args: &[&str]) -> Value {
        let output = tokio::process::Command::new(env!("CARGO_BIN_EXE_instantkv"))
            .args(["--url", &server.base])
            .args(args)
            .env("INSTANTKV_TOKEN", APP_TOKEN)
            .output()
            .await
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        serde_json::from_slice(&output.stdout).unwrap()
    }
    let saved = cli(
        &server,
        &[
            "remember",
            "Prefer Rust",
            "--key",
            "prefs/language",
            "--topic",
            "Preferences",
            "--tag",
            "local",
            "--metadata",
            "{\"source\":\"user\"}",
            "--occurred-at-ms",
            "1234",
        ],
    )
    .await;
    let recalled = cli(
        &server,
        &[
            "recall",
            "--topic",
            "preferences",
            "--query",
            "Rust",
            "--since-ms",
            "1234",
            "--until-ms",
            "1234",
        ],
    )
    .await;
    assert_eq!(recalled["items"][0]["memory"]["content"], "Prefer Rust");
    let ranked = cli(
        &server,
        &[
            "search",
            "preferred languages Rust",
            "--topic",
            "preferences",
        ],
    )
    .await;
    assert_eq!(ranked["items"][0]["memory"]["content"], "Prefer Rust");
    assert!(ranked["items"][0]["score"].as_f64().unwrap() > 0.0);
    assert_eq!(
        cli(&server, &["browse", "--limit", "1"]).await["items"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    let schema = cli(&server, &["schema", "--kind", "memory"]).await;
    assert_eq!(
        schema,
        serde_json::from_str::<Value>(include_str!("../../../examples/memory.schema.json"))
            .unwrap()
    );
    let revision = saved["revision"].as_u64().unwrap().to_string();
    let output = tokio::process::Command::new(env!("CARGO_BIN_EXE_instantkv"))
        .args([
            "--url",
            &server.base,
            "forget",
            "prefs/language",
            "--if-revision",
            &revision,
        ])
        .env("INSTANTKV_TOKEN", APP_TOKEN)
        .output()
        .await
        .unwrap();
    assert!(output.status.success());
    assert!(
        cli(&server, &["browse"]).await["items"]
            .as_array()
            .unwrap()
            .is_empty()
    );
}
