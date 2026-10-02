//! In-process memory: no model, HTTP server, async runtime or embeddings.
use instantkv_core::{
    Engine,
    config::Config,
    memory::{MemoryInput, MemoryQuery},
    model::Condition,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let data_dir = std::env::args().nth(1).ok_or("usage: memory DATA_DIR")?;
    let mut config = Config::parse(include_str!("../../../config/local.toml"))?;
    config.storage.data_dir = data_dir.into();
    let engine = Engine::open(config.clone())?;
    engine.remember(
        "knowledge",
        "preferences/language",
        MemoryInput {
            content: "Prefer Rust for local tools".into(),
            topic: Some("preferences".into()),
            tags: vec!["local".into()],
            ..Default::default()
        },
        None,
        Condition::Any,
    )?;
    drop(engine); // A new app session has no prompt or process memory.
    let engine = Engine::open(config)?;
    let memories = engine.recall(
        "knowledge",
        MemoryQuery {
            topic: Some("preferences".into()),
            query: Some("Rust".into()),
            ..Default::default()
        },
    )?;
    assert_eq!(
        memories.items[0].memory.content,
        "Prefer Rust for local tools"
    );
    println!("{}", serde_json::to_string_pretty(&memories)?);
    Ok(())
}
