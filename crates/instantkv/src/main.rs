use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use instantkv::{auth::read_secrets, client::Client, server};
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
    about = "Self-hosted memory for AI agents. Save, compact, restore."
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
    /// Create a ready-to-run config and private credentials. Never overwrites files.
    Init {
        #[arg(long, default_value = ".")]
        dir: PathBuf,
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
    /// Commit an immutable restore capsule and atomically advance its session pointer.
    Checkpoint {
        #[arg(long, default_value = "checkpoints")]
        namespace: String,
        #[arg(long)]
        file: PathBuf,
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
    Demo,
    /// Expose memory tools over MCP stdio; all operations use the authenticated HTTP API.
    Mcp,
    /// Print the checkpoint JSON Schema for editors and agent integrations.
    Schema,
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

#[tokio::main]
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
        Command::Init { dir } => init(&dir),
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
        Command::Demo => workflows::demo().await,
        Command::Schema => print_json(&schemars::schema_for!(CheckpointRequest)),
        command => {
            let secrets = read_secrets(&cli.secrets_file)?;
            let token = std::env::var("INSTANTKV_TOKEN")
                .ok()
                .or_else(|| std::env::var("INSTANTKV_APP_TOKEN").ok())
                .or_else(|| secrets.get("INSTANTKV_APP_TOKEN").cloned());
            let client = Client::new(&cli.url, token)?;
            match command {
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
                        (_, Some(file)) => fs::read(file)?,
                        _ => {
                            use std::io::Read;
                            let mut bytes = Vec::new();
                            std::io::stdin().take(1048577).read_to_end(&mut bytes)?;
                            bytes
                        }
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
                    let request: CheckpointRequest = serde_json::from_slice(&fs::read(file)?)
                        .context("invalid checkpoint JSON")?;
                    print_json(&client.checkpoint(&namespace, &request).await?)
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

fn init(dir: &Path) -> Result<()> {
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
    let credentials = format!(
        "INSTANTKV_APP_TOKEN={}\nINSTANTKV_READER_TOKEN={}\n",
        token(),
        token()
    );
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
    let template =
        include_str!("../../../config/instantkv.example.toml").replace("./data", ".instantkv/data");
    fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&config_path)?
        .write_all(template.as_bytes())?;
    println!("Created {}", config_path.display());
    println!("Private credentials: {}", secrets_path.display());
    println!("Next: cd {} && instantkv serve", dir.display());
    Ok(())
}
