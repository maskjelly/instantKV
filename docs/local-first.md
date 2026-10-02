# Local-first memory and ARM support

instantKV stores facts and checkpoints in your own data directory, beside your local model.
Storage and retrieval work offline after installation.
The service requires no account, embedding model or LLM API.
It makes no telemetry calls and has no automatic cloud fallback.
The public website and hosted demo are separate, optional services.

The source MVP adds `remember`, `recall`, `browse` and `forget`.
It provides indexed topic/tag/time retrieval and bounded keyword filtering.
Earlier release archives do not contain these tools.
[Memory guide](memory-mvp.md) · [Current measurements and targets](performance.md).

## Start on your machine

Build from this checkout with Rust 1.98+:

```sh
cargo install --path crates/instantkv --locked
mkdir my-local-memory
cd my-local-memory
instantkv init
instantkv serve
```

In another terminal, in the same directory:

```sh
instantkv put knowledge project/decision --value '{"content":"Keep memory on device"}'
instantkv get knowledge project/decision
instantkv checkpoint --file /path/to/checkpoint.json
instantkv restore --agent builder --session project-1
```

Use [the checkpoint example](../examples/checkpoint.json) for the last two commands.
Installation can download dependencies.
The server uses loopback HTTP by default. MCP stdio connects to that server.
[MCP setup](agents.md) · [Installation options](quickstart.md).

## Smaller default budgets

New `instantkv init` setups use [the local profile](../config/local.toml):

| Component               | Budget                                                    |
| ----------------------- | --------------------------------------------------------- |
| redb page cache         | 8 MiB                                                     |
| Scratch records         | 4 MiB of logical key + value bytes, at most 1,024 entries |
| Durable knowledge       | 64 MiB of logical bytes, at most 10,000 entries           |
| Durable checkpoints     | 16 MiB of logical bytes, at most 1,000 internal entries   |
| HTTP body               | 64 KiB including checkpoint JSON                          |
| In-flight HTTP requests | 32                                                        |
| Tokio async workers     | 2; blocking storage workers are separate                  |

These are component limits. They do not cap total process RAM or physical database size.
Indexes, buffers, worker stacks and database metadata add overhead.
A checkpoint uses a bundle and session pointer; both count toward its entry quota.
Durable namespaces reject writes at capacity. They do not automatically evict checkpoints.

The local profile requires bearer authentication on loopback. Other local processes can reach the port.

Keep `.instantkv/credentials.env` private.

instantKV does not encrypt storage. Operating-system disk encryption can protect the data at rest.

`init --profile agent` uses the earlier, larger quotas.
`init --profile swarm` creates shared knowledge and private worker namespaces.
Neither command changes an existing installation.
The optional `storage.cache_size_bytes` setting controls the redb cache.
If you omit it, redb uses its default.
[Configuration](configuration.md).

## ARM means a processor family, not one operating system

| Target                         | Current status                                                                   |
| ------------------------------ | -------------------------------------------------------------------------------- |
| Apple Silicon macOS            | Native build and local restart verification on this machine                      |
| Linux ARM64 / aarch64          | Native CI and static-musl packaging passed; physical-device measurements pending |
| Linux x86_64                   | Native CI and static-musl packaging passed                                       |
| iPhone / iPad                  | Native app integration, bindings and device tests planned                        |
| Android ARM64                  | Native app integration, bindings and device tests planned                        |
| 32-bit ARM / bare-metal boards | Not validated or supported by the release installer                              |

The Linux ARM64 binary requires a supported 64-bit Linux system, writable storage and sufficient RAM.
It does not establish iOS or Android support.
The CLI runs as a foreground server.
Native mobile integration must handle app suspension and sandbox storage.

Archive names are `instantkv-linux-arm64.tar.gz`, `instantkv-linux-x86_64.tar.gz` and `instantkv-darwin-arm64.tar.gz`.
CI builds the Linux ARM64 archive, but a release must publish it before the installer can download it.
Until publication, use a source build or a CI artifact.
The [Rust target reference](https://doc.rust-lang.org/rustc/platform-support/aarch64-unknown-linux-musl.html) describes the Linux ARM64 target.
Test the binary on your device.

## Measured Mac footprint

This is the earlier 2026-10-02 raw-KV smoke run, before the structured-memory MVP.
For the current source MVP use the [2026-10-03 memory measurements](performance.md).

The earlier test used an Apple M4 Pro with 24 GiB memory and macOS 27.0.
It ran on 2026-10-02 with a native release binary and the default local profile.

| Measurement                                           | Result                                           |
| ----------------------------------------------------- | ------------------------------------------------ |
| Native binary                                         | 7.6 MiB                                          |
| Idle server RSS                                       | 6.0 MiB                                          |
| Largest sampled server RSS                            | 7.6 MiB                                          |
| Durable records written and read after abrupt restart | 1,000 × 256-byte values, all verified            |
| Checkpoint and scratch                                | Checkpoint restored; scratch empty after restart |

This was one run of sequential loopback HTTP requests with keep-alive.
RSS samples covered startup, every 100 writes, completed writes and recovery.
They do not measure peak RSS or a fixed upper bound.
The results exclude the model and caller. Phone performance, battery use and real-agent recall quality were not measured.

The [raw report](benchmarks/2026-10-02-local/mac-arm64.json) records the source state, binary hash, hardware and samples.

Reproduce it from the checkout on macOS or Linux:

```sh
cargo build --release --locked -p instantkv
python3 scripts/local-smoke.py --output /tmp/instantkv-local-footprint.json
```

The script creates temporary state and credentials. It sends only loopback requests.
It terminates and restarts its own server, then verifies every stored value.
It removes temporary state and retains only the report at your output path.

## Embed the existing Rust core

`instantkv-core` exposes `Config`, `Engine` and checkpoint types.
A Rust app can call the core directly without Tokio, Axum, HTTP or MCP:

```rust
use instantkv_core::{config::Config, Engine, model::Condition};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut config = Config::parse(include_str!("../../../config/local.toml"))?;
    config.storage.data_dir = "./app-memory".into();
    let memory = Engine::open(config)?;
    memory.put("knowledge", "user/preference", br#"{"theme":"dark"}"#.to_vec(), None, Condition::Any)?;
    let saved = memory.get("knowledge", "user/preference")?;
    assert_eq!(saved.value, br#"{"theme":"dark"}"#);
    Ok(())
}
```

The [embedded example](../crates/instantkv-core/examples/local.rs) uses this API.

Run `cargo run -p instantkv-core --example local -- /tmp/instantkv-embedded`.
Keep synchronous storage calls outside the UI thread.

The host app controls its data path, cleanup scheduling, authorization and platform bindings.
HTTP credential grants do not protect direct core calls.

## What a collaboration could test

A local assistant can store preferences, decisions and task state, then checkpoint before a context reset.
Its runtime selects the records to save and retrieve.
instantKV does not automatically parse email, extract facts or perform semantic search.

Start with one local task: save a fact, checkpoint, clear context, restart and continue.
Measure process memory, task success and latency alongside the model.
Native phone bindings, encryption and app lifecycle need further design and tests.
