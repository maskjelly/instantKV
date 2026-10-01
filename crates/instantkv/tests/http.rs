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
    assert_eq!(tools["tools"].as_array().unwrap().len(), 7);
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
    child.kill().await.unwrap();
    child.wait().await.unwrap();
}
