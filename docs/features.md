# Implemented features

instantKV 0.1.1 is a self-hosted, single-node knowledge memory service for cloud
agents. Use the [quick start](quickstart.md) to run it and [the demo](demo.md) to
verify your setup. Managed hosting is in development; there is no public hosted
memory endpoint yet. The website hosts documentation, not your memory.

## Record memory

| Feature | How to use it |
|---|---|
| Exact recall | `put` and `get` with namespace + descriptive key |
| Prefix discovery | `list --prefix` returns metadata pages; values remain separate |
| Conditional creation | `put --if-absent` rejects overwriting an existing live key |
| Revision-safe update/delete | Use the observed revision with `--if-revision` |
| Explicit forgetting | `delete` removes an ordinary record and reclaims logical quota |
| Optional expiry | `put --ttl SECONDS`, subject to the namespace policy |
| Admission | Namespace checks JSON, UTF-8 or bytes; size limits bound keys and values |

The default profile has durable `knowledge` and `checkpoints`, plus RAM `scratch`.
Scratch uses TTL and FIFO eviction; it is empty after process restart. Durable
knowledge has no default TTL. Quotas count logical key/value bytes and entries,
not process RAM or physical database size. See [configuration](configuration.md).

## Compaction handoffs

A checkpoint atomically commits an immutable capsule, the session's latest
pointer and usage counters. Save essential continuation state inline: goal,
summary, constraints, decisions, open tasks and next action. Detailed records can
be referenced by namespace, key and expected revision.

Restore by checkpoint ID or by agent/session latest. The response has a byte
budget and reports `available`, `stale`, `missing` or `forbidden` references.
Expired referenced records are reported as missing.
References do not preserve historical record values. Identical checkpoint retries
are idempotent; stale latest-pointer revisions or conflicting payloads fail.

Delete old checkpoints deliberately with `delete-checkpoint`; the latest capsule
for each session is protected. Keep the checkpoint locator in runtime metadata
outside the compacted prompt. Automatic runtime compaction hooks are future work.
See [the memory contract](agent-memory.md).

## Shared knowledge and private agents

The swarm profile gives Alpha and Beta read-only shared knowledge plus private
knowledge and checkpoint namespaces. An operator publishes shared facts. Workers
cannot read sibling scopes or write shared knowledge. Add namespace/grant pairs
and restart to provision more workers. These are API permissions on one shared
process, not physical database replicas. See [cloud agents](cloud-agents.md).

## Three ways to connect

- [CLI](cli.md): setup, doctor, record/checkpoint operations, demos and benchmarks.
- [HTTP](http.md): bearer-authenticated routes with the same namespace policies.
- [MCP stdio](agents.md): seven typed model-callable tools; connects to an existing server.

All access paths use the same HTTP authorization and storage engine. Auth tokens
belong in a secret environment or private credentials file, never memory records.

## Operating the service

One Rust binary, strict TOML and one data directory. The non-root Docker setup
uses a persistent volume, read-only root filesystem and loopback host binding.
`check-config` validates policies; `doctor`, `/healthz`, namespace stats and
authenticated aggregate `/metrics` help verify the node.

An offline backup helper preserves configuration, credentials and database in a
private archive. The restore drill verifies a known checkpoint in an isolated
temporary volume. Follow [operations](operations.md) before upgrading.

## Planned

Managed hosting, distributed replicas, automatic run-completion consolidation,
semantic search, online snapshots, final-session retirement and a quality-focused
knowledge quality metrics are not implemented. The [roadmap](roadmap.md) and
[distributed proposal](distributed-memory.md) state the rollout gates.
