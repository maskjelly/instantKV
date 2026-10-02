# What you can do today

instantKV 0.1.2 stores agent knowledge and checkpoints locally, beside your model.
Use the [quick start](quickstart.md) to set it up, or try the
[live browser demo](https://instantkv.com/demo/) first. The demo uses real Rust
storage with temporary synthetic records; your own installation keeps memory
on your machine and works offline.

The four structured-memory tools below are implemented in the unreleased source
MVP. Build this checkout to try them. [Guide](memory-mvp.md),
[measured performance and targets](performance.md), [next milestones](roadmap.md).

## Record memory

| Feature | How to use it |
|---|---|
| Structured memory (source MVP) | `remember` / `recall` / `browse` / `forget`; topic, tags, event time, custom metadata |
| Indexed retrieval (source MVP) | Ordered topic/tag/time indexes; bounded literal keyword filtering and paginated values |
| Exact recall | `put` and `get` with namespace + descriptive key |
| Prefix discovery | `list --prefix` returns metadata pages; values remain separate |
| Conditional creation | `put --if-absent` rejects overwriting an existing live key |
| Revision-safe update/delete | Use the observed revision with `--if-revision` |
| Explicit forgetting | `delete` removes an ordinary record and reclaims logical quota |
| Optional expiry | `put --ttl SECONDS`, subject to the namespace policy |
| Input checks | Choose JSON, UTF-8 or raw bytes per namespace; set key and value size limits |

The default profile has durable `knowledge` and `checkpoints`, plus RAM `scratch`.
Scratch uses TTL and FIFO eviction; it is empty after process restart. Durable
knowledge has no default TTL. Quotas count logical key/value bytes and entries,
not process RAM or physical database size. See [configuration](configuration.md).

## Compaction handoffs

A checkpoint saves the context needed to continue a task: the goal, summary,
constraints, decisions, open tasks and next action. This note is the `capsule`
field in the API. Detailed facts stay in separate records, referenced by
namespace, key and expected revision. The checkpoint, session's latest pointer
and usage counters commit together in one database transaction.

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
process, not physical database replicas. See [local agents](cloud-agents.md).

## Three ways to connect

- [CLI](cli.md): setup, doctor, record/checkpoint operations, demos and benchmarks.
- [HTTP](http.md): bearer-authenticated routes with the same namespace policies.
- [MCP stdio](agents.md): eleven typed model-callable tools in the source MVP; connects to an existing server.

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

Local ARM device validation, native mobile integration and real-agent lifecycle
evaluation come first. Independent replicas and reviewing shared findings remain
optional future work. Semantic search, online
snapshots, final-session retirement and knowledge quality metrics are also
planned. See the [roadmap](roadmap.md) and
[distributed proposal](distributed-memory.md) for what must pass before they ship.
