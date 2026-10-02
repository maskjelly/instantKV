# Local-first memory and ARM support

Run instantKV beside your local model. Facts and checkpoints live in your own
data directory. Once installed, saving and recalling memory need no internet,
account, embedding model or LLM API. The memory service has no telemetry or
automatic cloud fallback. The public website and hosted demo are separate,
optional services; their network traffic is not part of local operation.

The source MVP adds **remember, recall, browse and forget**, with indexed
topic/tag/time retrieval and bounded keywords. [Memory API](memory-mvp.md) and
[new measured footprint plus targets](performance.md). Earlier release archives
do not include these new tools.

## Start on your machine

Build from this checkout with Rust 1.98+:

```sh
cargo install --path crates/instantkv --locked
mkdir my-local-memory
cd my-local-memory
instantkv init
instantkv serve
# Another terminal, same directory:
instantkv put knowledge project/decision --value '{"content":"Keep memory on device"}'
instantkv get knowledge project/decision
instantkv checkpoint --file /path/to/checkpoint.json
instantkv restore --agent builder --session project-1
```

Use [the checkpoint example](../examples/checkpoint.json) for the last two
commands. Installation can download dependencies; the running service uses
loopback HTTP by default. MCP stdio connects to that same local server.
[MCP setup](agents.md) and [full installation options](quickstart.md).

## Smaller default budgets

New `instantkv init` setups use [the local profile](../config/local.toml):

| Component | Budget |
|---|---|
| redb page cache | 8 MiB |
| Scratch records | 4 MiB of logical key + value bytes, at most 1,024 entries |
| Durable knowledge | 64 MiB of logical bytes, at most 10,000 entries |
| Durable checkpoints | 16 MiB of logical bytes, at most 1,000 internal entries |
| HTTP body | 64 KiB including checkpoint JSON |
| In-flight HTTP requests | 32 |
| Tokio async workers | 2; blocking storage workers are separate |

These are component budgets, not a total RAM or disk cap. Indexes, allocations,
HTTP buffers, worker stacks and database metadata add overhead. A checkpoint uses
an immutable bundle plus a session pointer, so entry quotas count both.
Durable namespaces reject full writes and never automatically evict checkpoints.

The local profile retains bearer authentication even on loopback. Other local
processes can reach the port; keep `.instantkv/credentials.env` private. Storage
is not encrypted by instantKV; use operating-system disk encryption if needed.

`init --profile agent` retains the earlier larger quotas. `init --profile swarm`
creates shared knowledge and per-agent private scopes. Neither changes an existing
installation. `storage.cache_size_bytes` is optional: old configs keep redb's
default. Adjust the [configuration](configuration.md) for your workload.

## ARM means a processor family, not one operating system

| Target | Current status |
|---|---|
| Apple Silicon macOS | Native build and local restart verification on this machine |
| Linux ARM64 / aarch64 | Native GitHub CI job, static-musl packaging and installer path added; CI and physical-device validation pending |
| Linux x86_64 | Existing native CI and static-musl binary path |
| iPhone / iPad | Native app integration, bindings and device tests planned |
| Android ARM64 | Native app integration, bindings and device tests planned |
| 32-bit ARM / bare-metal boards | Not validated or supported by the release installer |

A Linux ARM64 build is appropriate for a board running a 64-bit Linux OS,
subject to its RAM, writable storage and operating-system support. It does not
establish iOS or Android support. The current CLI is a foreground server; mobile
app suspension and sandbox storage need platform-specific handling.

Release archives are named `instantkv-linux-arm64.tar.gz`,
`instantkv-linux-x86_64.tar.gz` and `instantkv-darwin-arm64.tar.gz`.
The ARM64 Linux archive needs a successful CI run and release publication before
the installer can download it. Build from source until that archive exists.
The [Rust target reference](https://doc.rust-lang.org/rustc/platform-support/aarch64-unknown-linux-musl.html)
describes the Linux ARM64 target; test the actual binary on your device.

## Measured Mac footprint

This is the earlier 2026-10-02 raw-KV smoke run, before the structured-memory MVP.
For the current source MVP use the [2026-10-03 memory measurements](performance.md).

On 2026-10-02, a native release build with the default local profile ran on an
Apple M4 Pro Mac with 24 GiB unified memory and macOS 27.0:

| Measurement | Result |
|---|---|
| Native binary | 7.6 MiB |
| Idle server RSS | 6.0 MiB |
| Largest sampled server RSS | 7.6 MiB |
| Durable records written and read after abrupt restart | 1,000 × 256-byte values, all verified |
| Checkpoint and scratch | Checkpoint restored; scratch empty after restart |

This is one run of sequential keep-alive loopback HTTP requests. RSS was sampled
at startup, every 100 writes, after writes and after recovery; it is not peak RSS
or a fixed upper bound. The figures exclude the model and caller. This does not
measure phone performance, battery use or real-agent recall quality.
The [raw report](benchmarks/2026-10-02-local/mac-arm64.json) records the parent
commit, modified-working-tree status, binary hash, hardware and samples.

Reproduce it from the checkout on macOS or Linux:

```sh
cargo build --release --locked -p instantkv
python3 scripts/local-smoke.py --output /tmp/instantkv-local-footprint.json
```

The script creates temporary state and credentials, uses only loopback requests,
kills and restarts its own server, verifies every stored value and removes that
temporary state. It retains only the report at the requested output path.

## Embed the existing Rust core

`instantkv-core` exposes `Config`, `Engine` and checkpoint types. A Rust host app
can call it in process, without Tokio, Axum, HTTP or MCP:

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

The runnable [embedded example](../crates/instantkv-core/examples/local.rs) uses
this API. Run it from the checkout with
`cargo run -p instantkv-core --example local -- /tmp/instantkv-embedded`.
The core performs synchronous storage work: keep it off a UI thread. A host app
owns its data path, cleanup scheduling, authorization and platform bindings;
HTTP credential grants do not protect direct core calls.

## What a collaboration could test

An on-device assistant could use exact records for preferences, decisions and
task state, then checkpoint before a context reset. Its model/runtime still
chooses what to save and what keys to recall. instantKV does not parse email,
extract memories or perform semantic search automatically.

A useful first integration is one local task: save a fact, checkpoint, clear
context, restart, restore and continue. Measure the process footprint alongside
the model, task success and latency on the target device. Native phone bindings,
encryption and background lifecycle handling are work to scope with the app team.
