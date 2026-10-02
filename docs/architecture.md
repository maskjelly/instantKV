# Architecture and storage schema

Status: single-node implementation with an unreleased memory MVP. Updated: 2026-10-03.
[Verification history](checkpoints.md) records completed checks. Future work appears below.

Clients connect through HTTP, CLI or MCP. Permissions and limits apply before storage access.
Durable records use redb; scratch uses RAM. Rust apps can also embed the core directly.

## Stack decision

| Layer           | Choice                                                        | Why / constraint                                          |
| --------------- | ------------------------------------------------------------- | --------------------------------------------------------- |
| Core            | Rust 2024, minimum Rust 1.98                                  | Ownership and explicit memory/concurrency bounds          |
| HTTP            | Tokio + Axum                                                  | Async networking, middleware, graceful shutdown           |
| Durable storage | redb                                                          | Pure Rust, embedded ACID transactions; one writer         |
| Scratch         | Per-namespace Mutex + ordered maps                            | Atomic quotas; ordered prefix, deadline and FIFO indexes  |
| Configuration   | Serde + TOML                                                  | Strict fields and startup validation                      |
| Agent tools     | Official rmcp SDK, stdio → HTTP                               | Same auth and policy as every client                      |
| Deployment      | Binary / non-root Docker + volume                             | No database service or orchestration dependency           |
| Verification    | Fake-clock invariant tests + HTTP/MCP tests + CLI load client | Deterministic lifecycle checks and measured request paths |

Rust provides explicit control over memory and concurrency.
redb handles transactions and persistence inside the process, which permits one binary.
Go could also implement the service. Valkey could provide storage when a separate database is acceptable.
Language choice alone does not prove a speed advantage.

Sources: [Rust ownership](https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html),
[Axum](https://docs.rs/axum/latest/axum/),
[redb concurrency](https://docs.rs/redb/latest/redb/struct.Database.html).

## Boundaries and request paths

`instantkv-core` owns configuration policy, input validation, clocks, quotas, indexes, storage and checkpoint transactions.
`instantkv` provides HTTP, authentication, CLI, MCP, demos and benchmarks.
HTTP, CLI and MCP use the same permission layer.
An app that embeds the core must provide its own authorization.
[Local integration](local-first.md#embed-the-existing-rust-core).

Write flow: authorization → body limit → format/TTL/size validation → revision and quota validation → commit → success response.
A failed write preserves the old live value. Input validation can reclaim expired data.

Read flow: authorization → lookup → expiry test → value and revision.
Raw record lists return metadata only, with at most 1,000 items and bounded scans.
An extra empty page is possible. Continue until `next_cursor` is null.
Pages do not form a stable snapshot across writes.

A semaphore limits active requests and cleanup work.
Synchronous storage runs on `spawn_blocking`. A submitted task keeps its permit even after the HTTP deadline.
There is no unbounded writer queue.
A timed-out write can still commit.
[Tokio blocking-task behavior](https://docs.rs/tokio/latest/tokio/task/fn.spawn_blocking.html) explains this boundary.

After a timeout, inspect the revision or retry the same checkpoint ID and payload.

## Stored schema: format 1

All tables use `instantkv.redb`. Record and counter integers use little-endian u64 encoding.
Namespace names and ordinary keys cannot contain NUL. The composite record key is therefore unambiguous.

| Table             | Key                                                                   | Value                                                  |
| ----------------- | --------------------------------------------------------------------- | ------------------------------------------------------ |
| `records_v1`      | `namespace + NUL + key`                                               | 32-byte header + raw value bytes                       |
| `usage_v1`        | namespace                                                             | entry count, key/value bytes, revision high-water mark |
| `expiry_v1`       | padded UTC deadline + revision + composite key                        | composite record key                                   |
| `metadata_v1`     | format / namespace identity                                           | format version / storage mode + purpose                |
| `memory_index_v1` | namespace + index kind + optional normalized label + event time + key | composite structured-memory record key                 |

The record header contains revision, write time, expiry time and insertion order.
An expiry of zero means no expiry.
Ordinary JSON records accept your own fields without a fixed wrapper.
Namespaces can also accept raw bytes or UTF-8 text.

Structured-memory APIs use a `_instantkv_memory: 1` envelope in durable JSON records.
Time, topic and tag indexes change in the same transaction as records, quotas and expiry entries.
Deletion, replacement and expiry cleanup remove old index entries.
Recall reads indexes and values in one snapshot, with candidate, scan-byte and response limits.
Keyword filtering uses literal content; it requires no vector index or model.
[Memory shape and cursor contract](memory-mvp.md).

Checkpoint namespace reserved records:

```text
__checkpoint/<id>            -> JSON CheckpointRequest (immutable capsule + references)
__latest/<agent>/<session>    -> checkpoint ID bytes
```

The bundle, latest pointer and usage counters share one redb write transaction.
`expected_latest_revision = null` requires no prior pointer. Later saves use the last returned pointer revision.
Identical ID/payload retries do not rewind the pointer.
Old bundles can be deleted, but the current latest bundle is protected.
Deletion removes retry history; checkpoint IDs must remain unique.

Writes retain redb's [immediate durability](https://docs.rs/redb/latest/redb/enum.Durability.html).
Success follows commit. The filesystem and storage device must honor synchronization.
Restore reads the bundle and pointer in one snapshot.
Reference tests run separately and report current observations, not a snapshot of all referenced keys.

## Retention and accounting

RAM expiry uses a monotonic deadline. Durable expiry uses UTC and can change with the wall clock.
Reads hide expired records immediately. Cleanup has a batch limit.
Expired records count toward quota until removal.
RAM writes also run a bounded cleanup batch. Durable input validation does not scan all expired records.

Scratch eviction follows insertion order. Reads and live overwrites do not change that order.
Recreating an expired entry gives it a new insertion order.
Durable storage rejects over-quota writes and does not auto-evict.
Revisions do not reset after deletion, so stale conditions cannot match a recreated key.

Quotas count stored key/value bytes and entries, including checkpoint bundles and pointers.
They exclude allocator overhead, process RSS, indexes and physical database size.
Deleted disk pages can be reused. Deletion does not provide secure erasure.

## Access and operations

Namespaces define API access boundaries. Agent and session labels are metadata.
Private workers need separate namespace grants. Grants also apply to referenced records.
The server loads credentials at startup and compares fixed-size token hashes.
The swarm profile gives workers read-only `shared` access and private record/checkpoint access.
The operator can access all swarm namespaces.

Legacy namespace/operation shorthand remains supported. It cannot be combined with explicit grants.
Checkpoint saves require readable reference namespaces. Restore uses current GET grants.
[Swarm setup](cloud-agents.md).

Disabled authentication requires loopback. Remote access uses SSH tunneling or an HTTPS proxy.
Logs exclude request bodies and tokens. Metrics report aggregate counters.

Health reports a running listener after successful startup validation and database opening.
It does not periodically test disk writes.
Framework parsing errors can be plain text; service errors use a JSON object.
One process must own each data file.
[Backup and upgrades](operations.md).

## Future proposals

1. Connect a real runtime's compaction hooks and evaluate task continuation.
2. Add session retirement, online backup and deeper fault tests.
3. Measure writer contention, expiry delay and memory growth before adding storage concurrency features.
4. Implement the [distributed proposal](distributed-memory.md) in stages.
   Start with export/import, immutable baselines and private overlays. Add reviewed publication before synchronization.
5. Evaluate ranked keyword search and local embeddings with real tasks.

Topic/tag/time indexes and bounded literal keywords work in the source MVP.
Semantic search, automatic failover, a custom write-ahead log and Redis compatibility remain separate design choices.
