<p align="center"><img src="docs/assets/blueprint-social.svg" width="900" alt="instantKV: local-first memory for AI agents"></p>

<p align="center">
<a href="https://github.com/maskjelly/instantKV/actions/workflows/ci.yml"><img src="https://github.com/maskjelly/instantKV/actions/workflows/ci.yml/badge.svg" alt="Rust checks"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-606873?style=flat-square" alt="MIT license"></a>
<img src="https://img.shields.io/badge/Rust-1.98%2B-606873?style=flat-square" alt="Rust 1.98 or later">
</p>

# instantKV

**Local memory for AI agents. One Rust binary. No cloud dependency.**

Save facts, preferences and task state on your device. Find memories by topic,
tag, time or keywords. Rank documents with BM25 search. Keep them across sessions and server restarts.
Your runtime chooses what to save and adds retrieved facts to the model context.
Storage and retrieval work offline after installation.

[Website](https://instantkv.com) · [Memory guide](docs/memory-mvp.md) ·
[Quick start](docs/quickstart.md) · [Benchmarks](https://instantkv.com/benchmarks/) · [Roadmap](docs/roadmap.md)

**Source MVP, unreleased.** Build from source for the new memory tools.
Older release archives contain the original KV and checkpoint tools.
Native phone integration is planned.

## Start locally

From this checkout, with Rust 1.98 or later:

```sh
cargo install --path crates/instantkv --locked
mkdir my-local-memory
cd my-local-memory
instantkv init
instantkv serve
```

Open another terminal in the same directory:

```sh
instantkv remember "Prefer Rust for local tools" --key preferences/language --topic preferences --tag local
instantkv recall --topic preferences --query Rust
instantkv search "preferred language for local tooling" --limit 10
instantkv browse --limit 10
instantkv forget preferences/language
```

Setup creates private credentials and stores data in `.instantkv/data`.
The server listens on `127.0.0.1:8080`. Installation can download dependencies;
the running memory service needs no account, model API or embedding service.

[Docker setup](docs/quickstart.md#docker-is-optional) · [Connect through MCP](docs/agents.md)

## What you get

| Feature             | Behavior                                                                |
| ------------------- | ----------------------------------------------------------------------- |
| Five memory tools   | `remember`, `recall`, `search`, `browse`, `forget`                      |
| Structured records  | Content, topic, tags, event time and custom JSON metadata               |
| Indexed retrieval   | Topic/tag/time indexes, literal filters and bounded BM25 relevance ranking |
| Task checkpoints    | Save the goal and next action before a context reset; restore afterward |
| Private namespaces  | Share project facts while each agent keeps separate notes               |
| Configurable limits | Storage quotas, expiry, request limits and query budgets                |
| Integration         | HTTP, CLI, twelve MCP tools or an embedded Rust core                    |

`search` ranks content with English stemming and OR terms. `recall --query` applies literal AND filters.
Ranked queries accept up to 16 KiB. Long questions select up to 64 indexed terms.
Check `query_reduced` and `truncated`. WAND skips low-scoring postings within fixed work limits.
Use `search QUERY --expand` for optional light English expansion, or
`--expansion-term WORD` for related terms from your app. Expansion stays off by default.
Embedding search and automatic extraction remain planned.
Records and indexes change in one redb transaction, including updates, deletion and expiry cleanup.

[API and limits](docs/memory-mvp.md) · [HTTP](docs/http.md) · [CLI](docs/cli.md)

## Measured performance

| Full dataset | Scored questions | instantKV Recall@10 | SQLite FTS5 | Supermemory local |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval-S, source sessions | 500 | 95.13% | 95.43% | Incomplete |
| LoCoMo, source turns | 1,533 | 57.66% | 57.19% | 57.97% |
| BEIR SciFact, documents | 300 | 81.43% | Not run | 74.80% |
| BEIR ArguAna, documents | 1,406 | 76.96% | Not run | 56.40% |
| BEIR NFCorpus, documents | 323 | 15.31% | Not run | 17.08% |

All 500 LongMemEval-S questions and all ten LoCoMo histories were used.
LoCoMo queried 1,986 questions; 1,533 have scored positive source labels.
The 446 adversarial questions and seven unresolved references are excluded only
from positive-evidence recall. All five full memory retrieval files had zero
failures and zero truncations. Independent `pytrec_eval` checks used official source labels.

These are **retrieval scores, not end-to-end answer accuracy**. Full native LongMemEval-S QA scored **85.20%** (426/500) with zero
API failures and a 95% confidence interval of 82.0–88.2%. This uses the official
judge rubric with GPT-6 Luna as reader and judge, not official leaderboard model parity.
[QA settings and raw outputs](docs/benchmarks/2026-10-04-full-retrieval/qa-summary.json). Competitor QA remains incomplete. The initial model runs hit API rate limits and are not valid QA comparisons.
SQLite has slightly higher observed LongMemEval-S recall. Local Supermemory has
slightly higher LoCoMo recall. No statistically significant win is established.

Supermemory local v0.0.8 uses direct embedding retrieval without model extraction,
query rewriting or reranking. It does not represent the hosted product.
BEIR controls are separate same-host runs recorded on 3 October. ArguAna has
688 truncated and 1,149 reduced queries; none were rejected. Expansion is off by default.

[Full retrieval report and raw rankings](docs/benchmarks/2026-10-04-full-retrieval/README.md) ·
[BEIR reports](docs/benchmarks/2026-10-04-search/README.md) · [Engineering notes](docs/memory-benchmark-notes.md).

Three fresh databases, 10,000 memories per run, 512-byte content plus metadata.
Warm sequential loopback HTTP; concurrency one. Immediate durable commits.

| Measurement | Result across three runs |
| --- | --- |
| Native binary | 8.31 MiB |
| Idle server RSS | 6.34–6.36 MiB |
| Largest sampled server RSS | 20.88 MiB |
| Topic query p95 | 0.152–0.173 ms |
| Durable save p95 | 6.665–6.923 ms |
| Exact recovery after abrupt restarts | 30,000 of 30,000 memories |

Full retrieval server RSS: 14.34 MiB on LongMemEval-S and 11.25 MiB on LoCoMo.
RSS samples do not measure peak RAM. Timings include the HTTP client and server.
[Recovery samples](docs/benchmarks/2026-10-04-search/mac-arm64.json) · [Methodology](docs/benchmarks.md).

## Small by default

The local profile uses an 8 MiB redb cache, 4 MiB scratch quota and 32 active requests.
Durable knowledge has a 64 MiB logical quota and a 10,000-record limit.
These are component limits, not a total RAM or disk cap.

Scratch uses RAM and expiry; it is empty after a restart.
Durable knowledge and checkpoints remain in the database. Full durable namespaces reject writes.

Use `init --profile swarm` for shared facts and private worker namespaces.
Use `init --profile agent` for larger quotas.
[Configuration](docs/configuration.md) · [Local use and device support](docs/local-first.md)

## Continue work after a context reset

Save a checkpoint before clearing context. Wait for success, then keep its locator outside the prompt.
Restore the checkpoint before continuing. Fetch detailed records as needed.
The checkpoint and the session's latest pointer commit together.

<img src="docs/assets/lifecycle.png" width="1100" alt="Save a checkpoint and restore task state after a context reset">

The runtime saves the goal, progress and next action. It restores that state before
continuing. The engine provides storage; it does not resume a model by itself.
[Swarm setup](docs/cloud-agents.md) · [Checkpoint contract](docs/agent-memory.md) · [Backup guide](docs/operations.md)

## Next steps

| Priority           | Planned work                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------- |
| Real local agents  | Evaluate preferences and task continuation with the [Ollama example](examples/local-llm.py) |
| ARM devices        | Measure latency, RSS and recovery on a named Linux ARM64 board                              |
| Native phones      | Add Swift/Kotlin bindings; test storage, lifecycle and battery use                          |
| Portable memory    | Add export, import and schema migration tools                                               |
| Retrieval quality  | Improve paraphrase and multi-hop recall; finish full QA and remaining official suites                       |

Linux x86_64, Linux ARM64 and macOS ARM64 passed [source MVP CI](https://github.com/maskjelly/instantKV/actions/runs/37138251395).
Physical ARM-board measurements and native phone support remain pending.

Initial ARM-board goals: indexed recall p95 ≤5 ms, durable save p95 ≤20 ms,
idle RSS ≤12 MiB and loaded RSS ≤32 MiB. These are unverified targets for the
[defined 10,000-memory workload](docs/performance.md#next-device-targets--not-yet-measured).

Independent replicas, shared-update review and managed hosting remain optional future work.
[Roadmap](docs/roadmap.md) · [Distributed proposal](docs/distributed-memory.md)

## Build and contribute

Rust + Tokio + Axum + redb. MIT license.
KV means keys and values for agent knowledge; the model's inference KV cache stays in its runtime.

[Architecture](docs/architecture.md) · [Contributor guide](CONTRIBUTING.md) ·
[Security](SECURITY.md) · [Changelog](CHANGELOG.md) · [Verification history](docs/checkpoints.md)
