<p align="center"><img src="docs/assets/blueprint-social.svg" width="900" alt="instantKV: local-first memory for AI agents"></p>

<p align="center">
<a href="https://github.com/maskjelly/instantKV/actions/workflows/ci.yml"><img src="https://github.com/maskjelly/instantKV/actions/workflows/ci.yml/badge.svg" alt="Rust checks"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-606873?style=flat-square" alt="MIT license"></a>
<img src="https://img.shields.io/badge/Rust-1.98%2B-606873?style=flat-square" alt="Rust 1.98 or later">
</p>

# instantKV

[Website](https://instantkv.com) · [Start guide](https://instantkv.com/docs/quickstart/)
· [Memory demo](https://instantkv.com/demo/) · [Benchmarks](https://instantkv.com/benchmarks/) · [Documentation](https://instantkv.com/docs/)

**Local-first memory for AI agents. Keep the work on your device.**

instantKV keeps facts, preferences and unfinished tasks beside your local model.
Use **remember, recall, browse and forget**. Retrieve by **topic, tag, event time
or literal keywords**, then checkpoint the goal and next step before compaction.
Storage and recall work
offline once installed: no account, cloud service, embedding model or LLM API is
required. The memory service makes no telemetry calls.

One Rust binary with an embedded database. The default local profile binds to
loopback, generates private credentials and uses smaller resource budgets.
Connect through HTTP, CLI or eleven MCP tools. For Rust applications,
`instantkv-core` also exposes the storage engine directly, without an HTTP server.

Apple Silicon macOS is tested locally. Linux ARM64 has a native CI build and
packaging path; device validation is still needed. Native iOS/Android integration
is planned. See [local use, ARM targets and limits](docs/local-first.md).
MIT licensed; run it on hardware you already own.

**Source MVP, unreleased:** the indexed-memory API is implemented in this checkout.
Build from source; older release archives do not include it.
[Memory API and local model integration](docs/memory-mvp.md) ·
[Measured performance and next targets](docs/performance.md) · [Roadmap](docs/roadmap.md).

Three fresh 10,000-memory runs on an M4 Pro measured topic-query p95 at
**0.134–0.190 ms** and largest sampled server RSS at **19.5 MiB**. All 30,000
memories were verified after abrupt restarts. Synthetic, warm, sequential local
HTTP; excludes the model and phones. [Raw evidence](docs/benchmarks/2026-10-03-memory/mac-arm64.json).

## Who it's for

- Local LLM apps that need persistent facts outside the context window.
- Coding agents that need to resume unfinished tasks after compaction or restart.
- Multiple local agents sharing project facts with separate private notes.
- Developers adding memory to an existing runtime through MCP, HTTP or Rust.

Your runtime chooses what to save. Structured memory supports indexed topic/tag/time
retrieval and bounded content keyword filtering. Exact-key/prefix KV APIs remain.
Semantic search and automatic memory extraction are future work.
[How instantKV compares with other memory tools →](docs/choosing-instantkv.md)

## The swarm memory model

<img src="docs/assets/swarm.png" width="1100" alt="Implemented single-server topology: operator publishes shared knowledge; Alpha and Beta read shared records and write their own isolated knowledge and checkpoints">

Working today: agents read shared knowledge, write their own notes and save durable
checkpoints. Each request checks that worker's permissions. Add namespaces and
credentials for more agents. All workers use one server today; independent replicas
and automatic consolidation are planned below.
[Local agents and shared memory →](docs/cloud-agents.md)

## Start locally

With Rust 1.98+, install the native binary from this checkout:

```sh
cargo install --path crates/instantkv --locked
mkdir my-local-memory
cd my-local-memory
instantkv init
instantkv serve
# In another terminal, in the same directory:
instantkv remember "Prefer Rust for local tools" --topic preferences --tag local
instantkv recall --topic preferences --query Rust
instantkv browse --limit 10
```

Setup creates credentials automatically and stores data in `.instantkv/data`.
After installation, these operations need no internet connection.
[Binary install, Docker and first checkpoint →](docs/quickstart.md)

The default `local` profile budgets an 8 MiB redb cache and 4 MiB of logical scratch
data, with 32 in-flight requests. Those are component budgets, not a total RAM cap.
The new [M4 Pro memory runs](docs/performance.md) measured an 8.0 MiB native binary,
6.17–6.20 MiB idle RSS and 19.5 MiB largest sampled RSS. These measurements are
specific to that workload, not a device-independent RAM guarantee.

## Where we are going

1. **Real local-agent recall:** evaluate saved preferences and task continuation
   after fresh context and restarts. An [Ollama tool-loop example](examples/local-llm.py)
   is included; real model-quality results are pending.
2. **Native mobile embedding:** Swift/Kotlin bindings, app lifecycle, sandbox
   storage, backup/encryption design and battery measurements. The Rust core is
   embeddable today; native phone integration is planned.
3. **Portable, hackable memory:** app-defined metadata works now. Export/import,
   schema migration tooling and optional richer local retrieval are next.

Initial targets on a named 4 GiB Linux ARM64 board: indexed recall p95 ≤5 ms,
durable save p95 ≤20 ms, idle RSS ≤12 MiB and loaded RSS ≤32 MiB under the
documented 10,000-memory workload. **Goals, not measured ARM/phone results.**
[Workload, acceptance gates and limits](docs/performance.md#next-device-targets--not-yet-measured).

Use `init --profile agent` for larger quotas or `init --profile swarm` for shared
knowledge and separate worker credentials. Existing configurations stay unchanged.

## See it work

[**Open the memory demo →**](https://instantkv.com/demo/)
Replay 100,000 real Mac cache writes at 2× animation speed, then recall a cached
storage response. The measured result stays **42,517 writes/s**, with **0.328 ms
PUT p50**; playback never scales performance numbers. Three runs per mode,
330,000 writes and 24 exact reads, zero errors.
[Mac hardware, limits and all raw reports](docs/demo-results/2026-10-02-mac/README.md).

Select **Live VPS** to write up to 100,000 temporary cache records or 10,000 durable records. Clear the
writer's local context, retrieve an exact key in the separate reader, or open the
reader in a new tab. The demo uses real Rust storage and shows how many records
were saved, how much data was written and how long requests took. Watch throughput,
latency percentiles and the live request trace. Replay is labeled separately
from live storage; no account needed.

<img src="docs/assets/live-demo.svg" width="1100" alt="Live demo request flow: browser writer and reader, Cloudflare Worker, private VPC and QUIC tunnel, isolated coordinator, Rust HTTP API and real RAM or durable redb storage">

[Demo architecture and measurement boundaries](docs/live-demo.md).
For durable compaction handoffs and restart verification:

```sh
instantkv demo --swarm
# Or: ./scripts/kv.sh demo --swarm
```

The demo starts its own server and two clients with separate credentials. Both
read shared facts; each writes private notes. It checks that a worker can't read
the other's notes or overwrite shared facts. Then it saves Alpha's checkpoint,
clears simulated context, kills the server and restores from the same database.
No model API key is needed.
[Demo walkthrough and example output →](docs/demo.md)

## Survive compaction

<img src="docs/assets/lifecycle.png" width="1100" alt="Park reusable facts, commit a checkpoint, keep the locator outside compacted context, restore the capsule and fetch details by key">

Save the goal, constraints, decisions, unfinished tasks and next action in a
checkpoint. Its short context note is called a `capsule` in the API. Keep detailed
facts in separate records and refer to them by key and revision.

Wait until the save succeeds. Keep the checkpoint ID outside the prompt so
compaction can't erase it. After compaction, load the checkpoint first, then
fetch the records it points to.
[Connect your agent through MCP →](docs/agents.md)

## Three kinds of memory

| Namespace type | Purpose | Restart behavior |
|---|---|---|
| Shared + private knowledge | Facts, decisions, sources; exact key recall | Durable; no default TTL |
| Private checkpoints | Immutable capsules and atomic session latest pointers | Durable; never auto-evicted |
| Optional scratch | Temporary working data | RAM; TTL and FIFO eviction |

The swarm profile ships `shared`, `alpha`, `beta`, and a checkpoint namespace for
each worker. Default `instantkv init` gives a single agent `knowledge`,
`checkpoints`, and `scratch`. All namespace names and quotas are configurable.

- **Safe handoff:** capsule + latest pointer + quota counters commit together.
- **Small restores:** essential context inline; versioned references fetched on demand.
- **Controlled sharing:** per-namespace permissions and conditional revision writes.
- **Bounded storage:** quotas, size/TTL limits, indexed expiry and admission limits.
- **Agent access:** eleven typed MCP tools; HTTP and CLI use the same policies.

## Architecture

<img src="docs/assets/architecture.png" width="1100" alt="Local or remote agents use HTTP, CLI or MCP; grants and bounded policy route durable knowledge/checkpoints to redb and optional scratch to RAM; stored record and atomic checkpoint schema">

**Rust + Tokio + Axum + redb.** Rust suits the bounded storage and concurrency
core; redb supplies durable transactions without a separate database service.
[Design and schema](docs/architecture.md) · [Configuration](docs/configuration.md)
· [API contract](docs/agent-memory.md) · [Engineering inspirations](docs/inspirations.md)

## Measure it

Against the running Docker swarm instance:

```sh
./scripts/kv.sh bench --namespace alpha --operation get --requests 5000 --concurrency 16
./scripts/kv.sh bench --namespace alpha --operation put --requests 1000 --concurrency 8
```

Real HTTP keep-alive requests; reports throughput, p50/p95/p99, and errors.
Durable writes keep immediate durability enabled. Checkpoint benchmarks should
use a disposable instance. [Workloads and recorded results →](docs/benchmarks.md)

The original single-agent profile was measured on a busy shared 4-vCPU VPS;
medians of three runs, zero errors:

| Operation | Successful req/s | p50 / p99 |
|---|---:|---:|
| Scratch GET, 512 bytes | 3,708 | 1.88 / 47.36 ms |
| Durable PUT, 512 bytes | 744 | 5.80 / 57.65 ms |
| Capsule restore | 3,324 | 2.24 / 48.54 ms |

These loopback measurements include existing host load. They do not measure
public HTTPS or distributed swarms. Raw reports and environment are linked above.

## Next: smaller local integrations

The priority is to validate Linux ARM64 hardware, measure memory and battery use
under real local-agent workloads, and integrate the core into native mobile apps.
A real-model save → compact → restore → continue evaluation comes before claims
about better recall. The proposed multi-device workflow below remains optional.

### Optional multi-device knowledge consolidation

<img src="docs/assets/distributed.png" width="1100" alt="Future proposal: canonical knowledge base sends a versioned baseline to independent workers; completed runs submit shareable deltas; durable consolidation validates sources and conflicts before publishing the next baseline; quality metrics track sources, freshness and recall">

The plan is to fork past memory snapshots into independent agent branches. Give
several agents the same starting point and let them explore different directions.
They keep private notes, share findings during their runs and follow accepted
updates from the shared knowledge base. A scoped activity feed shows what other
agents are working on and which updates they have seen. Sources and conflicts
are reviewed before findings become shared facts; completion flushes the remaining
changes. Offline agents catch up from a saved cursor.

<img src="docs/assets/memory-branches.svg" width="1100" alt="Future proposal: historical snapshots seed independent agent branches; findings enter review during runs; accepted facts update shared knowledge and return to agents through a replayable change feed">

We'll measure useful knowledge by checked facts, source coverage and recall
success, with freshness and unresolved conflicts visible. Storing more text alone
doesn't show improvement. This distributed workflow is a proposal.
[Detailed design, schema and rollout gates →](docs/distributed-memory.md)

## Project status

Early single-node release. Shared knowledge and private agent namespaces work today. Physical
replication, automatic consolidation, semantic search and automatic runtime
compaction hooks remain future work. The restart demo simulates context clearing;
a real-model lifecycle evaluation and deeper power/disk-failure audit remain open.
[Implemented and next](docs/roadmap.md) · [Operations and backup](docs/operations.md)

Here, KV means keys and values for agent knowledge. An inference KV cache stores
a model's attention tensors; those stay in the model runtime.

## Contribute

[Development guide](CONTRIBUTING.md) · [Security reports](SECURITY.md)
· [Changelog](CHANGELOG.md) · [Verified checkpoints](docs/checkpoints.md)
· [Session request audit](docs/request-audit.md)

MIT licensed. Original Monolith identity, four diagrams and matching editable sources:
[docs/assets](docs/assets/README.md).
