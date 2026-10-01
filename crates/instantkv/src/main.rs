use clap::{Parser, Subcommand};
use instantkv_core::config::Config;
use std::{fs, path::PathBuf, process::ExitCode};

#[derive(Parser)]
#[command(
    version,
    about = "instantKV deployment configuration tools (server not implemented yet)"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Validate deployment policies without starting a server or reading secrets.
    CheckConfig {
        #[arg(short, long, default_value = "config/instantkv.example.toml")]
        config: PathBuf,
    },
}

fn main() -> ExitCode {
    let Cli { command } = Cli::parse();
    let Command::CheckConfig { config } = command;
    let result = fs::read_to_string(&config)
        .map_err(|error| format!("cannot read {}: {error}", config.display()))
        .and_then(|input| Config::parse(&input));
    match result {
        Ok(parsed) => {
            println!(
                "Valid configuration: {} ({} namespace(s))",
                config.display(),
                parsed.namespaces.len()
            );
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("Invalid configuration: {error}");
            ExitCode::FAILURE
        }
    }
}
