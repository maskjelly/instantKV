use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand, ValueEnum};
use instantkv::{auth::read_secrets, client::Client, server};
use instantkv_core::memory::{MemoryInput, MemoryQuery, RememberRequest};
use instantkv_core::search::SearchQuery;
use instantkv_core::{config::Config, model::CheckpointRequest};
use std::{
    fs,
    net::SocketAddr,
    path::{Path, PathBuf},
};

mod workflows;

#[derive(Parser)]
#[command(
    version,
    about = "Local-first memory for AI agents. Save, compact, restore offline."
)]
struct Cli {
    #[arg(long, global = true, default_value = "http://127.0.0.1:8080")]
    url: String,
    /// NAME=value credentials file; environment variables take precedence.
    #[arg(long, global = true, default_value = ".instantkv/credentials.env")]
    secrets_file: PathBuf,
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Save an indexed fact, preference or observation. Create-only unless --if-revision is supplied.
    Remember {
        content: String,
        #[arg(long, default_value = "knowledge")]
        namespace: String,
        #[arg(long)]
        key: Option<String>,
        #[arg(long)]
        topic: Option<String>,
        #[arg(long = "tag")]
        tags: Vec<String>,
        /// App-defined JSON object; not searched by the MVP.
        #[arg(long, default_value = "{}")]
        metadata: String,
        #[arg(long)]
        occurred_at_ms: Option<u64>,
        #[arg(long)]
        ttl: Option<u64>,
        #[arg(long, requires = "key")]
        if_revision: Option<u64>,
    },
    /// Retrieve structured memory by topic, tag, time range or keywords.
    Recall(Retrieval),
    /// Rank relevant memories with BM25 and English stemming. No embedding model.
    Search {
        text: String,
        #[arg(long)]
        expand: bool,
        #[arg(long = "expansion-term")]
        expansion_terms: Vec<String>,
        #[command(flatten)]
        filters: Retrieval,
    },
    /// Browse structured memories newest first; follow next_cursor until null.
    Browse(Retrieval),
    /// Delete a structured memory and its indexes atomically.
    Forget {
        key: String,
        #[arg(long, default_value = "knowledge")]
        namespace: String,
        #[arg(long)]
        if_revision: Option<u64>,
    },
    /// Create a ready-to-run config and private credentials. Never overwrites files.
    Init {
        #[arg(long, default_value = ".")]
        dir: PathBuf,
        #[arg(long, value_enum, default_value = "local")]
        profile: Profile,
    },
    /// Create private local state on first use, then start the memory server.
    Start {
        /// Directory for config, credentials and durable memory.
        #[arg(long, default_value = ".")]
        dir: PathBuf,
        #[arg(long)]
        bind: Option<SocketAddr>,
    },
    /// Start the memory server with persistent knowledge and disposable scratch.
    Serve {
        #[arg(short, long, default_value = "instantkv.toml")]
        config: PathBuf,
        #[arg(long)]
        bind: Option<SocketAddr>,
        #[arg(long)]
        data_dir: Option<PathBuf>,
    },
    /// Validate deployment policies without opening storage or reading secrets.
    CheckConfig {
        #[arg(short, long, default_value = "instantkv.toml")]
        config: PathBuf,
    },
    /// Check configuration, credential availability, and server connectivity.
    Doctor {
        #[arg(short, long, default_value = "instantkv.toml")]
        config: PathBuf,
        #[arg(long)]
        offline: bool,
    },
    /// Save a value from a file, --value, or stdin. JSON is the default profile.
    Put {
        namespace: String,
        key: String,
        #[arg(long, conflicts_with = "file")]
        value: Option<String>,
        #[arg(long)]
        file: Option<PathBuf>,
        #[arg(long)]
        ttl: Option<u64>,
        #[arg(long, conflicts_with = "if_absent")]
        if_revision: Option<u64>,
        #[arg(long)]
        if_absent: bool,
    },
    /// Recall exact bytes. The revision is written to stderr, data to stdout.
    Get {
        namespace: String,
        key: String,
    },
    /// Discover metadata without loading every memory value.
    List {
        namespace: String,
        #[arg(long, default_value = "")]
        prefix: String,
        #[arg(long, default_value_t = 100)]
        limit: usize,
        #[arg(long)]
        cursor: Option<String>,
    },
    Delete {
        namespace: String,
        key: String,
        #[arg(long)]
        if_revision: Option<u64>,
    },
    Stats {
        namespace: String,
    },
    /// Commit immutable checkpoint context and atomically advance its session pointer.
    Checkpoint {
        #[arg(long, default_value = "checkpoints")]
        namespace: String,
        /// JSON file, or '-' for stdin (default).
        #[arg(long, default_value = "-")]
        file: PathBuf,
    },
    /// Delete an old checkpoint; refuses to delete a session's latest checkpoint.
    DeleteCheckpoint {
        #[arg(long, default_value = "checkpoints")]
        namespace: String,
        id: String,
    },
    /// Restore by stable checkpoint ID or by agent/session's latest checkpoint.
    Restore {
        #[arg(long, default_value = "checkpoints")]
        namespace: String,
        #[arg(long, conflicts_with_all = ["agent", "session"])]
        id: Option<String>,
        #[arg(long, requires = "session")]
        agent: Option<String>,
        #[arg(long, requires = "agent")]
        session: Option<String>,
        #[arg(long, default_value_t = 32768)]
        max_bytes: usize,
    },
    /// Run a self-contained HTTP save/compaction/restart/restore demonstration.
    Demo {
        /// Demonstrate shared knowledge, isolated agents, and restored private checkpoints.
        #[arg(long)]
        swarm: bool,
    },
    /// Expose memory tools over MCP stdio; all operations use the authenticated HTTP API.
    Mcp,
    /// Run MCP stdio with its own local memory server. No separate serve command.
    McpLocal {
        /// Persistent config, credentials and database directory; independent of client cwd.
        #[arg(long)]
        dir: PathBuf,
    },
    /// Print authoritative JSON schemas for editors and agent integrations.
    Schema {
        #[arg(long, default_value = "checkpoint", value_parser = ["checkpoint", "memory"])]
        kind: String,
    },
    /// Measure real HTTP latency and throughput, with durable writes kept durable.
    Bench {
        #[arg(long, default_value = "scratch")]
        namespace: String,
        #[arg(long, default_value = "get", value_parser = ["get", "put", "checkpoint", "restore"])]
        operation: String,
        #[arg(long, default_value_t = 5000)]
        requests: usize,
        #[arg(long, default_value_t = 16)]
        concurrency: usize,
        #[arg(long, default_value_t = 512)]
        value_bytes: usize,
        #[arg(long)]
        output: Option<PathBuf>,
    },
}

#[derive(clap::Args)]
struct Retrieval {
    /// All whitespace-separated terms must occur in content (case-insensitive).
    #[arg(long)]
    query: Option<String>,
    #[arg(long, default_value = "knowledge")]
    namespace: String,
    #[arg(long)]
    topic: Option<String>,
    #[arg(long)]
    tag: Option<String>,
    /// Inclusive event time in Unix milliseconds.
    #[arg(long)]
    since_ms: Option<u64>,
    #[arg(long)]
    until_ms: Option<u64>,
    #[arg(long, default_value_t = 20)]
    limit: usize,
    #[arg(long, default_value_t = 16384)]
    max_bytes: usize,
    #[arg(long)]
    cursor: Option<String>,
}

#[derive(Clone, Copy, ValueEnum)]
enum Profile {
    Local,
    Agent,
    Swarm,
}

#[tokio::main(worker_threads = 2)]
async fn main() -> std::process::ExitCode {
    tracing_subscriber::fmt()
        .with_writer(std::io::stderr)
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "instantkv=info".into()),
        )
        .init();
    match run(Cli::parse()).await {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("Error: {error:#}");
            std::process::ExitCode::FAILURE
        }
    }
}

async fn run(cli: Cli) -> Result<()> {
    match cli.command {
        Command::Init { dir, profile } => init(&dir, profile),
        Command::Start { dir, bind } => {
            let config_path = dir.join("instantkv.toml");
            let secrets_path = dir.join(".instantkv/credentials.env");
            if !config_path.exists() && !secrets_path.exists() {
                initialize(&dir, Profile::Local, true)?;
            }
            let dir = fs::canonicalize(&dir)?;
            let mut config = load_config(&config_path)?;
            if config.storage.data_dir.is_relative() {
                config.storage.data_dir = dir.join(&config.storage.data_dir);
            }
            if let Some(bind) = bind {
                config.server.bind = bind;
            }
            config.validate().map_err(anyhow::Error::msg)?;
            println!("Memory directory: {}", dir.display());
            println!(
                "In another terminal, from that directory: instantkv remember \"A fact to keep\""
            );
            server::serve(config, &secrets_path).await
        }
        Command::McpLocal { dir } => {
            let config_path = dir.join("instantkv.toml");
            let secrets_path = dir.join(".instantkv/credentials.env");
            if !config_path.exists() && !secrets_path.exists() {
                initialize(&dir, Profile::Local, true)?;
            }
            let dir = fs::canonicalize(&dir)?;
            let mut config = load_config(&config_path)?;
            if config.storage.data_dir.is_relative() {
                config.storage.data_dir = dir.join(&config.storage.data_dir);
            }
            let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await?;
            config.server.bind = listener.local_addr()?;
            config.validate().map_err(anyhow::Error::msg)?;
            let secrets = read_secrets(&secrets_path)?;
            let token = std::env::var("INSTANTKV_APP_TOKEN")
                .ok()
                .or_else(|| secrets.get("INSTANTKV_APP_TOKEN").cloned())
                .context(
                    "local MCP requires INSTANTKV_APP_TOKEN in its credentials file or environment",
                )?;
            let client = Client::new(&format!("http://{}", config.server.bind), Some(token))?;
            let (ready_tx, ready_rx) = tokio::sync::oneshot::channel();
            let server =
                server::serve_with_listener_ready(config, &secrets_path, listener, Some(ready_tx));
            tokio::pin!(server);
            tokio::select! {
                result = &mut server => return result,
                result = ready_rx => result.context("local MCP server exited before it was ready")?,
            }
            // Both transports share one process. EOF closes the local server too.
            tokio::select! {
                result = &mut server => result,
                result = instantkv::mcp::serve(client) => result,
            }
        }
        Command::CheckConfig { config } => {
            let parsed = load_config(&config)?;
            println!(
                "Valid configuration: {} ({} namespaces)",
                config.display(),
                parsed.namespaces.len()
            );
            Ok(())
        }
        Command::Serve {
            config,
            bind,
            data_dir,
        } => {
            let mut parsed = load_config(&config)?;
            if let Some(bind) = bind {
                parsed.server.bind = bind;
            }
            if let Some(data_dir) = data_dir {
                parsed.storage.data_dir = data_dir;
            }
            parsed.validate().map_err(anyhow::Error::msg)?;
            server::serve(parsed, &cli.secrets_file).await
        }
        Command::Demo { swarm } => {
            if swarm {
                workflows::swarm_demo().await
            } else {
                workflows::demo().await
            }
        }
        Command::Schema { kind } => {
            if kind == "memory" {
                print_json(
                    &serde_json::json!({"remember": schemars::schema_for!(RememberRequest),
                    "recall": schemars::schema_for!(MemoryQuery),
                    "search": schemars::schema_for!(SearchQuery)}),
                )
            } else {
                print_json(&schemars::schema_for!(CheckpointRequest))
            }
        }
        command => {
            let secrets = read_secrets(&cli.secrets_file)?;
            let token = std::env::var("INSTANTKV_TOKEN")
                .ok()
                .or_else(|| std::env::var("INSTANTKV_APP_TOKEN").ok())
                .or_else(|| secrets.get("INSTANTKV_APP_TOKEN").cloned());
            let client = Client::new(&cli.url, token)?;
            match command {
                Command::Remember {
                    content,
                    namespace,
                    key,
                    topic,
                    tags,
                    metadata,
                    occurred_at_ms,
                    ttl,
                    if_revision,
                } => {
                    let metadata = serde_json::from_str(&metadata)
                        .context("metadata must be a JSON object")?;
                    print_json(
                        &client
                            .remember(
                                &namespace,
                                &RememberRequest {
                                    key,
                                    memory: MemoryInput {
                                        content,
                                        topic,
                                        tags,
                                        metadata,
                                        occurred_at_ms,
                                    },
                                    ttl_seconds: ttl,
                                    if_revision,
                                },
                            )
                            .await?,
                    )
                }
                Command::Search {
                    text: query,
                    expand,
                    expansion_terms,
                    filters: input,
                } => {
                    if input.query.is_some() {
                        bail!("search uses its positional query; omit --query");
                    }
                    print_json(
                        &client
                            .search(
                                &input.namespace,
                                &SearchQuery {
                                    query,
                                    expand,
                                    expansion_terms,
                                    topic: input.topic,
                                    tag: input.tag,
                                    since_ms: input.since_ms,
                                    until_ms: input.until_ms,
                                    limit: input.limit,
                                    max_bytes: input.max_bytes,
                                    cursor: input.cursor,
                                },
                            )
                            .await?,
                    )
                }
                Command::Recall(input) | Command::Browse(input) => print_json(
                    &client
                        .recall(
                            &input.namespace,
                            &MemoryQuery {
                                topic: input.topic,
                                tag: input.tag,
                                query: input.query,
                                since_ms: input.since_ms,
                                until_ms: input.until_ms,
                                limit: input.limit,
                                max_bytes: input.max_bytes,
                                cursor: input.cursor,
                            },
                        )
                        .await?,
                ),
                Command::Forget {
                    key,
                    namespace,
                    if_revision,
                } => {
                    client.forget(&namespace, &key, if_revision).await?;
                    println!("Forgotten");
                    Ok(())
                }
                Command::Mcp => instantkv::mcp::serve(client).await,
                Command::Doctor { config, offline } => {
                    let parsed = load_config(&config)?;
                    instantkv::auth::Auth::load(&parsed, &secrets)?;
                    println!("Config and credentials: OK");
                    if !offline {
                        println!("Server: {}", client.health().await?);
                    }
                    Ok(())
                }
                Command::Put {
                    namespace,
                    key,
                    value,
                    file,
                    ttl,
                    if_revision,
                    if_absent,
                } => {
                    let bytes = match (value, file) {
                        (Some(value), _) => value.into_bytes(),
                        (_, Some(file)) => read_input(&file)?,
                        _ => read_input(Path::new("-"))?,
                    };
                    print_json(
                        &client
                            .put(&namespace, &key, bytes, ttl, if_revision, if_absent)
                            .await?,
                    )
                }
                Command::Get { namespace, key } => {
                    let (bytes, revision) = client.get(&namespace, &key).await?;
                    use std::io::Write;
                    std::io::stdout().write_all(&bytes)?;
                    eprintln!("revision: {revision}");
                    Ok(())
                }
                Command::List {
                    namespace,
                    prefix,
                    limit,
                    cursor,
                } => print_json(
                    &client
                        .list(&namespace, &prefix, limit, cursor.as_deref())
                        .await?,
                ),
                Command::Delete {
                    namespace,
                    key,
                    if_revision,
                } => {
                    client.delete(&namespace, &key, if_revision).await?;
                    println!("Deleted");
                    Ok(())
                }
                Command::Stats { namespace } => print_json(&client.stats(&namespace).await?),
                Command::Checkpoint { namespace, file } => {
                    let request: CheckpointRequest = serde_json::from_slice(&read_input(&file)?)
                        .context("invalid checkpoint JSON")?;
                    print_json(&client.checkpoint(&namespace, &request).await?)
                }
                Command::DeleteCheckpoint { namespace, id } => {
                    client.delete_checkpoint(&namespace, &id).await?;
                    println!("Deleted checkpoint");
                    Ok(())
                }
                Command::Restore {
                    namespace,
                    id,
                    agent,
                    session,
                    max_bytes,
                } => {
                    if let Some(id) = id {
                        print_json(&client.restore(&namespace, &id, max_bytes).await?)
                    } else if let (Some(agent), Some(session)) = (agent, session) {
                        print_json(
                            &client
                                .restore_latest(&namespace, &agent, &session, max_bytes)
                                .await?,
                        )
                    } else {
                        bail!("restore requires --id or both --agent and --session");
                    }
                }
                Command::Bench {
                    namespace,
                    operation,
                    requests,
                    concurrency,
                    value_bytes,
                    output,
                } => {
                    workflows::bench(
                        client,
                        &namespace,
                        &operation,
                        requests,
                        concurrency,
                        value_bytes,
                        output.as_deref(),
                    )
                    .await
                }
                _ => unreachable!("handled before constructing the client"),
            }
        }
    }
}

fn read_input(path: &Path) -> Result<Vec<u8>> {
    use std::io::Read;
    let mut bytes = Vec::new();
    if path == Path::new("-") {
        std::io::stdin().take(1048577).read_to_end(&mut bytes)?;
    } else {
        fs::File::open(path)?
            .take(1048577)
            .read_to_end(&mut bytes)?;
    }
    if bytes.len() > 1048576 {
        bail!("CLI input exceeds 1 MiB");
    }
    Ok(bytes)
}

fn load_config(path: &Path) -> Result<Config> {
    Config::parse(
        &fs::read_to_string(path).with_context(|| {
            format!("cannot read {}; run 'instantkv init' first", path.display())
        })?,
    )
    .map_err(anyhow::Error::msg)
}
fn print_json(value: &impl serde::Serialize) -> Result<()> {
    println!("{}", serde_json::to_string_pretty(value)?);
    Ok(())
}

fn init(dir: &Path, profile: Profile) -> Result<()> {
    initialize(dir, profile, false)
}

fn initialize(dir: &Path, profile: Profile, quiet: bool) -> Result<()> {
    let config_path = dir.join("instantkv.toml");
    let private = dir.join(".instantkv");
    let secrets_path = private.join("credentials.env");
    if config_path.exists() || secrets_path.exists() {
        bail!("config or credentials already exist; init never overwrites them");
    }
    fs::create_dir_all(&private)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&private, fs::Permissions::from_mode(0o700))?;
    }
    let token = || {
        format!(
            "{}{}",
            uuid::Uuid::new_v4().simple(),
            uuid::Uuid::new_v4().simple()
        )
    };
    let template = match profile {
        Profile::Local => include_str!("../../../config/local.toml"),
        Profile::Agent => include_str!("../../../config/instantkv.example.toml"),
        Profile::Swarm => include_str!("../../../config/swarm.toml"),
    }
    .replace("./data", ".instantkv/data");
    let parsed = Config::parse(&template).map_err(anyhow::Error::msg)?;
    let credentials: String = parsed
        .auth
        .principals
        .iter()
        .map(|principal| format!("{}={}\n", principal.token_env, token()))
        .collect();
    let mut options = fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    use std::io::Write;
    options
        .open(&secrets_path)?
        .write_all(credentials.as_bytes())?;
    fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&config_path)?
        .write_all(template.as_bytes())?;
    if !quiet {
        println!("Created {}", config_path.display());
        println!("Private credentials: {}", secrets_path.display());
        println!("Next: cd {} && instantkv serve", dir.display());
    }
    Ok(())
}
