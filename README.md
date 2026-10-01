# instantKV

A fast memory store for AI agents: **park knowledge before compaction, restore
working context afterward, and retrieve saved knowledge whenever needed.**

You choose how long memory lives, what gets rejected, who can access it, and
whether it survives restart.

## Status

**Working Rust memory server and CLI.** Durable storage, atomic checkpoints,
scratch eviction, TTL, scoped authentication, HTTP, a real restart demo, and a
benchmark client, and MCP stdio tools are implemented. Container deployment is
being verified on Linux. See [agent integration](docs/agents.md).

## The agent workflow

1. **During work:** save facts, decisions, sources, and next steps under known keys.
2. **Before compaction:** commit a durable checkpoint containing essential context.
3. **After compaction:** restore a short context capsule and references to details.
4. **Later:** recall exact keys or list a prefix without reloading everything.

The agent runtime must call checkpoint/restore at the right time. A memory server
alone cannot detect or intercept compaction.

## What you control

| Requirement | Deployment setting |
|---|---|
| How long data stays | Default TTL, maximum TTL, whether TTL is required |
| How fast expired data is removed | Cleanup interval and bounded cleanup batches |
| What happens at capacity | Reject writes, or explicitly evict oldest cache entries |
| What data is accepted | Bytes, UTF-8, or JSON; key/value size limits |
| How much data can be stored | Per-namespace entry and byte quotas |
| Who can access it | API-key principals, namespace scopes, operation permissions |
| How it is accessed | HTTP, then MCP tools and CLI through the same policy layer |
| What survives restart | Memory cache or durable embedded storage per namespace |

Expiry hides data immediately at its deadline. Cleanup removes it afterward.
Eviction removes unexpired data when an explicitly configured cache fills.

## Recommended stack

**Rust + Tokio + Axum + redb + TOML.**

- Rust gives control over memory and concurrency: a good fit for this project.
- Tokio/Axum handle networking and HTTP; redb handles durable transactions.
- Durable knowledge and checkpoints; temporary memory gets its own cache namespace.
- One server binary, one TOML file, one data directory.
- Start with a single node. Measure before adding sharding or a new protocol.

See the [architecture](docs/architecture.md), [agent memory contract](docs/agent-memory.md),
and [ordered build plan](docs/roadmap.md).

## Quickstart

```sh
cargo install --git https://github.com/maskjelly/instantKV --locked instantkv
instantkv init
instantkv serve
```

In a second terminal in the same directory:

```sh
instantkv put knowledge project/storage --value '{"content":"Use Rust + redb"}'
instantkv get knowledge project/storage
```

Run `instantkv demo` for a self-contained save → compact → kill → restart → restore
proof. See [setup and benchmark commands](docs/quickstart.md).

## Configuration checks

Install Rust with Cargo, then run from this directory:

```sh
cargo run -p instantkv -- check-config --config config/instantkv.example.toml
cargo run -p instantkv -- check-config --config config/local-cache.toml
cargo test --workspace --locked
```

`check-config` checks policy structure and relationships. It does not start a
listener, inspect a database, or check that referenced secrets exist.

- [Agent profile](config/instantkv.example.toml): permanent durable knowledge and
  checkpoints, temporary scratch memory, scoped writer and reader credentials.
- [Local cache profile](config/local-cache.toml): loopback only, no authentication,
  memory storage, five-minute TTL, oldest-entry eviction at capacity.
- [Configuration semantics](docs/configuration.md): exact meaning of each policy.

## Files

```text
crates/instantkv-core/   Shared configuration and validation
crates/instantkv/        CLI; future server entry point
config/                 Checked example deployment policies
docs/architecture.md    Components, guarantees, trade-offs
docs/agent-memory.md    Memory records and checkpoint/restore contract
docs/configuration.md   Policy rules and units
docs/roadmap.md          Implementation order and acceptance checks
.github/workflows/      Build, format, lint, and test checks
```

**First implementation milestone:** memory GET/PUT/DELETE with correct TTL and
quota accounting. See the roadmap for the release gates.
