# Local memory roadmap

The source MVP is implemented and unreleased.
The priority is a small memory layer that local apps can embed, configure and extend.
Native phone support and model-quality improvements need further tests.

## Direction and acceptance gates

| Stage                     | Current status                                              | Evidence needed                                                                                  |
| ------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Structured local memory   | Implemented in source                                       | Topic/tag/time retrieval, bounded keywords, update/delete/expiry/restart tests                   |
| Actual local-agent use    | Ollama tool-loop example available; evaluation pending      | Preferences/tasks used correctly after fresh context + restart; model and tool success reported  |
| Linux ARM64 validation    | Native CI and packaging passed; device measurements pending | Named-board benchmarks, cold/warm latency, RSS and recovery                                      |
| Native phone embedding    | Rust core available; Swift/Kotlin bindings planned          | Android/iOS build, sandbox paths, suspension/relaunch, backup/encryption design, battery profile |
| Portable app memory       | Custom metadata works; export/import and migrations planned | Versioned bundles, size limits, provenance, round-trip integrity, index rebuild                  |
| Richer optional retrieval | BM25 ranking implemented; local embeddings proposed         | Task-recall improvement, dependency/index size, latency and power costs                          |

The [performance plan](performance.md) records Mac measurements and unverified ARM-board targets.
Its 10,000-memory workload has these initial targets:

- Indexed recall p95: at most 5 ms.
- Immediate durable save p95: at most 20 ms.
- Idle server RSS: at most 12 MiB.
- Loaded server RSS: at most 32 MiB.

These targets exclude model inference and app overhead.

Daily memory operations use five tools.
Custom JSON metadata, typed APIs and configurable limits provide extension points.
The memory service remains usable offline.

## Working in this source checkout

- [x] Rust workspace, strict configuration and CI.
- [x] Durable redb knowledge and bounded RAM scratch cache.
- [x] Atomic quotas, indexed TTL cleanup, FIFO eviction, revision conditions.
- [x] Exact recall and bounded prefix metadata pages.
- [x] Structured `remember`, `recall`, `search`, `browse` and `forget` through core, HTTP, CLI and MCP.
- [x] Ordered topic/tag/time indexes with atomic record/index updates and cleanup.
- [x] Transactional BM25 postings with English stemming, bounded scoring and ranked cursors.
- [x] Accept 16 KiB questions, select up to 64 indexed terms and report reduction.
- [x] WAND pruning with bounded index reads; optional low-weight English and app-defined expansion.
- [x] Bounded keyword filtering, response byte budget and filter-bound cursors.
- [x] Custom metadata, explicit event time, create-only saves and revision protection.
- [x] Immutable checkpoint + latest pointer in one immediate transaction.
- [x] Idempotent retries, bounded restore, visible stale/missing/forbidden references.
- [x] Old-checkpoint deletion protecting the latest restore point.
- [x] Scoped credentials, HTTP, CLI setup/doctor, twelve MCP stdio tools.
- [x] Shared knowledge and isolated agents using per-namespace grants.
- [x] Ready-made swarm init profile and two-agent HTTP isolation/restart demo.
- [x] Demo with simulated compaction and real server kill/restart.
- [x] HTTP benchmark client for recall, save, checkpoint and restore.
- [x] Checksummed Linux/macOS binaries and hardened Docker quick-start.
- [x] Offline backup and isolated restore drill.
- [x] Three VPS benchmark runs per workload with raw reports and environment.
- [x] Cloudflare website with setup, feature, contributor and benchmark pages.
- [x] Static evidence site with full retrieval results and independent score receipts.
- [x] Three 10,000-memory local HTTP runs and exact recovery after abrupt restarts.

Deployment and measured results are recorded in [operations](operations.md),
[benchmarks](benchmarks.md) and [verification checkpoints](checkpoints.md).

## Retrieval improvement gates

The [evaluation notes](memory-benchmark-notes.md) report both wins and losses.
The suite uses fixed settings; it does not tune the engine to test labels.

| Work | Status and acceptance evidence |
| --- | --- |
| Long questions | Implemented: 16 KiB input and up to 64 selected indexed terms; query reduction stays visible. Evaluate rank fusion as separate future work |
| Bounded BM25 scoring | WAND pruning and exhaustive synthetic correctness check implemented; broader held-out and peak-allocation evaluation remains planned |
| Source context | Optional adjacent turns and parent-session links; evidence coverage improves within an explicit output byte cap |
| Changed facts | App-defined correction links and source/event dates; tests retrieve the current fact and its source history |
| Optional semantic adapter | Held-out paraphrase gains; report model/index size, RAM, latency and energy; default service stays model-free |
| Full memory evaluation | Full LongMemEval and real-agent answers; separate evidence recall, answer accuracy, abstention and tool failures |

Rows marked implemented are in the source MVP. Other changes remain planned.
The default service stays model-free; optional expansion remains off.
Phone performance remains unverified.

## Next release gates

| Work                         | Acceptance evidence                                                                             |
| ---------------------------- | ----------------------------------------------------------------------------------------------- |
| Concrete agent runtime hooks | Real task → save → compact → restore → continue; locator survives outside prompt                |
| Failure injection            | Kill during save, disk-full and commit failure; latest pointer always old or complete new       |
| Retired sessions             | Explicit session retirement; reclaim final bundle/pointer without surprising active agents      |
| Storage operations           | Online backup/export, migration tooling and larger database recovery tests                      |
| Performance                  | Longer repeated runs across key counts, payloads, TTL backlogs, disk/RSS growth and concurrency |
| Observability                | Latency histograms, expiry lag, rejection counters and storage health probes                    |

## Local-first priorities

1. Validate the Linux ARM64 build on real devices, including low-memory boards.
2. Measure idle/loaded RSS, disk growth, latency and energy use with local LLM apps.
3. Integrate `instantkv-core` into native apps. Validate iOS/Android storage,
   lifecycle, sandbox paths and device-level backup before claiming phone support.
4. Run a real local-agent save → compact → restore → continue evaluation. The
   Ollama example provides the tool loop; actual inference results are pending.
5. Add optional export/import before multi-device synchronization.

The default local profile uses smaller limits, loopback access and private credentials.
The Rust core already works as an embedded library.
Native mobile bindings, packaging and device tests remain planned.
[Local-first use](local-first.md).

## Optional hosting

Local operation is the priority. Managed hosting is a possible later service.
There is no availability date or price.
The public website publishes static evidence. Run the source MVP locally for memory operations.
Hosting would need tenant isolation, backups, scoped setup and operational monitoring.

## Distributed knowledge consolidation

The proposal starts independent agent branches from a saved memory snapshot.
Agents can keep private notes and submit shared findings while they work.
A review service checks sources and conflicts before updating shared knowledge.
Connected agents can follow accepted updates and inspect permitted peer status.
[Design and failure cases](distributed-memory.md).

| Stage                                 | Scope                                                                                        | Status      |
| ------------------------------------- | -------------------------------------------------------------------------------------------- | ----------- |
| Shared knowledge + private namespaces | One server; read-only shared knowledge for workers                                           | Implemented |
| Authorized export/import              | Explicit portable knowledge bundles with source/hash validation                              | Proposed    |
| Baseline + private overlay            | Immutable baseline manifest on independent worker nodes                                      | Proposed    |
| Historical memory branches            | Fork any retained, authorized snapshot; preserve parent lineage and independent private work | Proposed    |
| Incremental findings                  | Idempotent batches during a run, review before publication, final completion flush           | Proposed    |
| Run-completion jobs                   | Idempotent uploads, durable state, retries and leases                                        | Proposed    |
| Consolidation                         | Deduplicate, summarize with sources, review conflicts, conditional publication               | Proposed    |
| Distributed sync                      | Restartable pull replication, offline/reconnect and tombstones                               | Proposed    |
| Connected agents + peer awareness     | Ordered replayable updates, saved cursors, scoped task status and stale-peer leases          | Proposed    |
| Knowledge quality metrics             | Validated facts, source coverage, freshness, conflicts and evaluated recall                  | Proposed    |

This distributed workflow is a proposal. It does not provide a current consensus database.
Automatic failover, a custom write-ahead log and Redis compatibility need separate designs and evidence.
Future work should address gaps found in real tasks and measurements.

## Full evaluation status — 4 October 2026

- Full LongMemEval-S retrieval: 500 questions. Native and matched-page SQLite complete.
- Full LoCoMo retrieval: all ten histories and 1,986 questions. Native, SQLite
  and local Supermemory complete; positive recall covers 1,533 questions.
- All five ranking files independently verified. Full native QA rescoring is pending.
- LongMemEval-V2, AMA-Bench, BEAM and 100K–10M+ record tests remain incomplete.
- Next work: paraphrase recall, multi-hop evidence, time and update correctness,
  then device tests. Use separate development sets; preserve all failures.

[Full results](benchmarks/2026-10-04-full-retrieval/README.md) · [Evaluation policy](evaluation-policy.md).
