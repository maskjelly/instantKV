//! In-process local memory, without an HTTP server or model calls.
use instantkv_core::{Engine, config::Config, model::Condition};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut config = Config::parse(include_str!("../../../config/local.toml"))?;
    config.storage.data_dir = std::env::args()
        .nth(1)
        .ok_or("usage: cargo run -p instantkv-core --example local -- DATA_DIR")?
        .into();
    let memory = Engine::open(config)?;
    memory.put(
        "knowledge",
        "user/preference",
        br#"{"theme":"dark"}"#.to_vec(),
        None,
        Condition::Any,
    )?;
    let saved = memory.get("knowledge", "user/preference")?;
    assert_eq!(saved.value, br#"{"theme":"dark"}"#);
    println!("Local memory recalled at revision {}", saved.revision);
    Ok(())
}
