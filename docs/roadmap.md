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
- [x] Demo with simulated compaction and real server kill/restart.
- [x] HTTP benchmark client for recall, save, checkpoint and restore.
- [x] Checksummed Linux/macOS binaries and hardened Docker quick-start.
- [x] Offline backup and isolated restore drill.
- [x] Three VPS benchmark runs per workload with raw reports and environment.

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

Replication, semantic search, a custom WAL and Redis wire compatibility are not
promised. Prioritize proven recall gaps and measured limits first.
