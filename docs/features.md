# What you can do today

The current source stores local-agent knowledge and task checkpoints.
The five structured-memory tools are implemented but unreleased.
Earlier 0.1.2 archives contain only the original KV and checkpoint tools.
[Quick start](quickstart.md) · [Memory guide](memory-mvp.md) · [Performance](performance.md).

Read the [full retrieval results](benchmarks/2026-10-04-full-retrieval/README.md).

## Record memory

| Feature                        | How to use it                                                                          |
| ------------------------------ | -------------------------------------------------------------------------------------- |
| Structured memory (source MVP) | `remember` / `recall` / `search` / `browse` / `forget`; topic, tags, event time, custom metadata  |
| Indexed retrieval (source MVP) | Ordered topic/tag/time indexes; literal filtering and bounded BM25 relevance ranking |
| Exact recall                   | `put` and `get` with namespace + descriptive key                                       |
| Prefix discovery               | `list --prefix` returns metadata pages; values remain separate                         |
| Conditional creation           | `put --if-absent` rejects overwriting an existing live key                             |
| Revision-safe update/delete    | Use the observed revision with `--if-revision`                                         |
| Explicit forgetting            | `delete` removes an ordinary record and reclaims logical quota                         |
| Optional expiry                | `put --ttl SECONDS`, subject to the namespace policy                                   |
| Input checks                   | Choose JSON, UTF-8 or raw bytes per namespace; set key and value size limits           |

The default profile provides durable `knowledge`, durable `checkpoints` and RAM `scratch`.
Scratch uses TTL and first-in, first-out eviction. It is empty after a restart.
Durable knowledge has no default TTL.
Quotas count logical key/value bytes and entries, not total RAM or physical database size.
[Configuration](configuration.md).

## Compaction handoffs

A checkpoint stores the goal, summary, constraints, decisions, open tasks and next action.
The API calls this context note a `capsule`.
Detailed facts stay in records referenced by namespace, key and expected revision.
The checkpoint, latest pointer and usage counters commit in one transaction.

Restore accepts a checkpoint ID or the latest pointer for an agent/session.
The response has a byte budget.
References report `available`, `stale`, `missing` or `forbidden`. Expired references report `missing`.
References do not preserve old record values.
Identical checkpoint retries are idempotent; stale pointer revisions and conflicting payloads fail.

Use `delete-checkpoint` to remove an old checkpoint.
Keep the checkpoint locator in runtime metadata outside the prompt.

The latest checkpoint for each session is protected. Automatic compaction hooks are planned.
[Checkpoint contract](agent-memory.md).

## Shared knowledge and private agents

The swarm profile provides read-only shared facts and private knowledge/checkpoint namespaces for Alpha and Beta.
An operator writes shared facts. Workers cannot read sibling namespaces or write shared knowledge.
Additional workers need namespaces, grants, credentials and a restart.
All workers use one process and database.
[Swarm setup](cloud-agents.md).

## Three ways to connect

- [CLI](cli.md): setup, doctor, record/checkpoint operations, local examples and benchmarks.
- [HTTP](http.md): bearer-authenticated routes with the same namespace policies.
- [MCP stdio](agents.md): twelve typed model-callable tools in the source MVP; connects to an existing server.

CLI and MCP calls use HTTP authorization and the same storage engine.
Tokens belong in a private environment or credentials file, never memory records.
Rust apps can also call the core directly; the app must provide its own authorization.

## Operating the service

The service uses one Rust binary, TOML configuration and one data directory.
Docker uses a persistent volume, a read-only root filesystem and a loopback host port.
`check-config` validates policies. `doctor`, `/healthz`, namespace stats and authenticated `/metrics` help verify the node.

The offline backup helper saves configuration, credentials and the database in a private archive.
The restore test loads a known checkpoint in a temporary volume.
[Upgrade and backup steps](operations.md).

## Planned

The priorities are physical ARM-device tests, native phone integration and real-model evaluation.
Optional future work includes replicas, reviewed shared findings and semantic search.
Online snapshots, final-session retirement and knowledge-quality metrics are also planned.
[Roadmap](roadmap.md) · [Distributed proposal](distributed-memory.md).
