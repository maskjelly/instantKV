# Implemented and next

## Working now

- [x] Rust workspace, strict configuration and CI.
- [x] Durable redb knowledge and bounded RAM scratch cache.
- [x] Atomic quotas, indexed TTL cleanup, FIFO eviction, revision conditions.
- [x] Exact recall and bounded prefix metadata pages.
- [x] Immutable checkpoint + latest pointer in one immediate transaction.
- [x] Idempotent retries, bounded restore, visible stale/missing/forbidden references.
- [x] Old-checkpoint deletion protecting the latest restore point.
- [x] Scoped credentials, HTTP, CLI setup/doctor, seven MCP stdio tools.
- [x] Shared mother knowledge and isolated cloud agents using per-namespace grants.
- [x] Ready-made swarm init profile and two-agent HTTP isolation/restart demo.
- [x] Demo with simulated compaction and real server kill/restart.
- [x] HTTP benchmark client for recall, save, checkpoint and restore.
- [x] Checksummed Linux/macOS binaries and hardened Docker quick-start.
- [x] Offline backup and isolated restore drill.
- [x] Three VPS benchmark runs per workload with raw reports and environment.
- [x] Static Cloudflare website with setup, feature, contributor and benchmark pages.

Deployment and measured results are recorded in [operations](operations.md),
[benchmarks](benchmarks.md) and [verification checkpoints](checkpoints.md).

## Next release gates

| Work | Acceptance evidence |
|---|---|
| Concrete agent runtime hooks | Real task → save → compact → restore → continue; locator survives outside prompt |
| Failure injection | Kill during save, disk-full and commit failure; latest pointer always old or complete new |
| Retired sessions | Explicit session retirement; reclaim final bundle/pointer without surprising active agents |
| Storage operations | Online backup/export, migration tooling and larger database recovery tests |
| Performance | Longer repeated runs across key counts, payloads, TTL backlogs, disk/RSS growth and concurrency |
| Observability | Latency histograms, expiry lag, rejection counters and storage health probes |

## Managed hosting is in development

Managed hosting means we run the memory node and you connect your agents directly.
Self-hosting is available today; a public managed endpoint is not available yet.
There is no announced launch date or hosted pricing. The website is documentation
and benchmark infrastructure, separate from the future memory service.

Before launch: scoped credential provisioning, persistent tenant isolation,
resource budgets, verified backup/recovery, TLS, operational monitoring and the
failure-injection gates above. The open-source self-hosted service stays available.

## Distributed mothership direction

Each agent should receive a versioned baseline, retain its own private KV overlay,
and contribute shareable findings when its run completes. A durable consolidation
pipeline should deduplicate, validate sources, surface conflicts, and publish a
reviewed new mother baseline. [Design and proposed schema](distributed-memory.md).

| Stage | Scope | Status |
|---|---|---|
| Shared mother + private namespaces | One server; read-only mother for workers | Implemented |
| Authorized export/import | Explicit portable knowledge bundles with source/hash validation | Proposed |
| Baseline + private overlay | Immutable mother manifest on independent worker nodes | Proposed |
| Run-completion jobs | Idempotent uploads, durable state, retries and leases | Proposed |
| Consolidation | Deduplicate, summarize with sources, review conflicts, conditional publication | Proposed |
| Distributed sync | Restartable pull replication, offline/reconnect and tombstones | Proposed |
| Knowledge meter | Validated facts, source coverage, freshness, conflicts and evaluated recall | Proposed |

This is a distributed knowledge workflow proposal, not a shipped consensus KV.
Choose automatic failover only after availability requirements justify it.
Semantic search, a custom WAL and Redis wire compatibility are separate choices;
prioritize proven recall gaps and measured limits.
