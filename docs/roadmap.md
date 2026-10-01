# Build order

Each phase has a release gate. Checked items are implemented; others are planned.

## 0. Foundation — current scaffold

- [x] Rust workspace, shared config types, CLI config validator.
- [x] Agent-memory and disposable-cache deployment examples.
- [x] Configuration regression tests and CI workflow definition.
- [x] Architecture, memory contract, and policy documentation.

CI is configured but has not run on GitHub; this folder is not a Git repository yet.

## 1. Policy-correct memory core

- [ ] GET/PUT/DELETE, JSON envelope model, revisions and conditional updates.
- [ ] Fake clock, indexed expiry, atomic quotas, FIFO scratch eviction.
- [ ] Prefix discovery with cursor and response-size bounds.

**Gate:** failed admission preserves old values; overwrite/expiry/eviction maintain
usage counters; concurrent writes cannot exceed quotas or lose conditional updates.
Test TTL boundaries and replacing a record while old expiry is pending.

## 2. Durable handoff — product-critical

- [ ] redb records, expiry index, counters, namespace format/version metadata.
- [ ] Bounded database executor; immediate durable acknowledgements.
- [ ] Immutable checkpoint bundle + latest pointer in one transaction.
- [ ] Self-contained, bounded restore capsule; idempotent checkpoint retries.

**Gate:** kill/restart during save; recover complete old/new checkpoint. Simulate
disk-full and failed commits; never advance the pointer on failure. Compacted
context can resume without scratch state or expired references.

## 3. Usable server

- [ ] Tokio/Axum HTTP endpoints, API-key namespace/operation authorization.
- [ ] Request/body/queue limits, structured errors, readiness, graceful shutdown.
- [ ] Logs/metrics without memory content or credentials; offline backup/restore.
- [ ] Linux Docker image, persistent volume example, TLS proxy instructions.

**Gate:** unauthorized namespace access fails across all routes; overload stays
bounded; restore a verified backup after restart; validate release build in container.
Start with an offline backup while the database is closed; online backup comes later.

## 4. Agent integration

- [ ] MCP adapter tools: put/get/list/delete/checkpoint/restore.
- [ ] One real runtime integration storing bootstrap locators outside the prompt.
- [ ] Pre-compaction acknowledgement and post-compaction restoration, or explicit
  save/restore tools where runtime lifecycle hooks are unavailable.

**Gate:** real task → checkpoint → compaction → server restart → restore → continue.
Recover goal, constraints, decisions, sources, and next action; measure restore bytes
and time. Test failed saves and stale references visibly.

## 5. Measure, then optimize

- [ ] Separate exact recall, durable save, checkpoint, and restore benchmarks.
- [ ] Sweep concurrency, key counts, value sizes, TTL load, and disk latency.
- [ ] Record p50/p95/p99, throughput, RSS, disk growth, and expiry lag.
- [ ] Compare memory and durable modes on the same hardware and durability settings.

**Gate:** report environment and workload with every number. Choose performance
targets from the real agent workflow; add sharding/search only for measured needs.
