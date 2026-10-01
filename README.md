<p align="center"><img src="docs/assets/brand.png" width="900" alt="instantKV — Memory that survives compaction"></p>

<p align="center">
<a href="https://github.com/maskjelly/instantKV/actions/workflows/ci.yml"><img src="https://github.com/maskjelly/instantKV/actions/workflows/ci.yml/badge.svg" alt="Rust checks"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-20785f" alt="MIT license"></a>
<img src="https://img.shields.io/badge/Rust-1.98%2B-20785f" alt="Rust 1.98 or later">
</p>

# instantKV

**Park knowledge. Save a checkpoint. Compact. Restore and continue.**

A self-hosted KV memory service for AI agents, built in Rust. One binary, one
config, one data directory. HTTP, CLI, and MCP tools share the same permissions
and storage policies.

## Start using it

With Docker and Compose:

```sh
git clone https://github.com/maskjelly/instantKV.git
cd instantKV
./scripts/quickstart.sh
./scripts/kv.sh put knowledge project/storage --value '{"content":"Use Rust + redb"}'
./scripts/kv.sh get knowledge project/storage
```

Or install with Rust 1.98+:

```sh
cargo install --git https://github.com/maskjelly/instantKV --locked instantkv
instantkv init
instantkv serve
# In another terminal, in the same directory:
instantkv put knowledge project/storage --value '{"content":"Use Rust + redb"}'
instantkv get knowledge project/storage
```

Setup generates private credentials automatically. Docker retains them and the
database in a named volume. [Quick setup →](docs/quickstart.md)

## See it work

```sh
instantkv demo
# Or: ./scripts/kv.sh demo
```

The demo parks knowledge over HTTP, saves a capsule, clears simulated agent
context, kills its server process, restarts against the same database, and
asserts that the capsule and knowledge survived. Scratch must disappear.
No model API key is needed. [Demo walkthrough →](docs/demo.md)

## Three kinds of memory

| Namespace | Purpose | Restart behavior |
|---|---|---|
| `knowledge` | Facts, decisions, sources; exact key recall | Durable; no default TTL |
| `checkpoints` | Immutable capsules and atomic session latest pointers | Durable; never auto-evicted |
| `scratch` | Temporary working data | RAM; TTL and FIFO eviction |

- **Safe handoff:** capsule + latest pointer + quota counters commit together.
- **Small restores:** essential context inline; versioned references fetched on demand.
- **Shared memory:** ETags and conditional writes prevent lost updates.
- **Controlled storage:** namespace grants, admission limits, quotas, indexed expiry.
- **Agent access:** seven MCP tools with typed schemas; CLI also works over HTTP.

The runtime chooses when to save and restore, and keeps its locator outside
compacted prompt text. [Connect your agent →](docs/agents.md)

## Architecture

<img src="docs/assets/architecture.png" alt="Agent runtime to HTTP, CLI or MCP, shared policy, redb and RAM storage; atomic checkpoint schema" width="1100">

**Rust + Tokio + Axum + redb.** Rust suits the bounded storage and concurrency
core; redb supplies durable transactions without a separate database service.
[Design and schema](docs/architecture.md) · [Configuration](docs/configuration.md)
· [API contract](docs/agent-memory.md) · [Engineering inspirations](docs/inspirations.md)

## Measure it

```sh
instantkv bench --namespace scratch --operation get --requests 5000 --concurrency 16
instantkv bench --namespace knowledge --operation put --requests 1000 --concurrency 8
```

Real HTTP keep-alive requests; reports throughput, p50/p95/p99, and errors.
Durable writes keep immediate durability enabled. Checkpoint benchmarks should
use a disposable instance. [Workloads and recorded results →](docs/benchmarks.md)

Measured on a busy shared 4-vCPU VPS; medians of three runs, zero errors:

| Operation | Successful req/s | p50 / p99 |
|---|---:|---:|
| Scratch GET, 512 bytes | 3,708 | 1.88 / 47.36 ms |
| Durable PUT, 512 bytes | 744 | 5.80 / 57.65 ms |
| Capsule restore | 3,324 | 2.24 / 48.54 ms |

These loopback measurements include the existing host load; they are not a public
HTTPS capacity claim. Raw reports and the complete environment are in the link above.

## Project boundaries

Early single-node release. Stores application knowledge and compaction context;
model attention tensors stay with the inference runtime. No replication,
semantic search, automatic runtime hooks, or production fault-audit claim.
[Implemented and next](docs/roadmap.md) · [Operations and backup](docs/operations.md)

## Contribute

[Development guide](CONTRIBUTING.md) · [Security reports](SECURITY.md)
· [Changelog](CHANGELOG.md) · [Verified checkpoints](docs/checkpoints.md)

MIT licensed. Logo and editable architecture sources live in
[docs/assets](docs/assets/README.md).
