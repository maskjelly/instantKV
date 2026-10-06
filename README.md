# instantKV

**Open-source local AI memory. Install it and run it beside your agents.**

Save facts, preferences and task checkpoints. Retrieve them after a context reset
or restart. One Rust engine, with HTTP, CLI, MCP and an embedded core.
Your app decides what to save and how to use it. Storage and retrieval run locally
without a cloud API or embedding model. MIT licensed.

**Source MVP, unreleased.** Older release archives lack the structured-memory tools.
Use a source build for the commands below. Native phone support is planned.

## Start locally

With Rust 1.98 or later:

```sh
cargo install --git https://github.com/maskjelly/instantKV --locked instantkv
mkdir my-local-memory
cd my-local-memory
instantkv init
instantkv serve
```

In another terminal, from the same memory directory:

```sh
instantkv remember "Prefer Rust for local tools" --key preferences/language --topic preferences
instantkv search "preferred language for local tooling" --limit 10
instantkv recall --topic preferences
instantkv browse --limit 10
instantkv forget preferences/language
```

Setup creates private credentials and stores data in `.instantkv/data`.
The server binds to `127.0.0.1:8080`. Installation downloads source and dependencies.
From a local checkout, use `cargo install --path crates/instantkv --locked`.

[Setup guide](docs/quickstart.md) · [Connect through MCP](docs/agents.md) ·
[Embedded Rust example](crates/instantkv-core/examples/memory.rs) ·
[Agent-readable guides](https://instantkv.com/llms.txt)

## What works

- Structured memories: content, topic, tags, event time and custom JSON metadata.
- Topic/tag/time indexes, literal filters and bounded BM25 keyword ranking.
- Atomic record/index writes, revision checks, expiry and configurable quotas.
- Task checkpoints with an atomic latest pointer and bounded restore.
- Namespace permissions through HTTP, CLI and MCP; an in-process Rust core.

`search` uses English stemming and OR terms. `recall --query` uses literal AND filters.
Inspect `query_reduced` and `truncated`; bounded search may return incomplete rankings.
The service does not extract facts automatically or resume a model by itself.

[Memory contract and limits](docs/memory-mvp.md) · [Checkpoint contract](docs/agent-memory.md)

## Evidence and limits

Published reports cover full LongMemEval-S and LoCoMo retrieval, model QA,
local storage timings and restart recovery. LongMemEval-S source-session
Recall@10 is **95.13%**. Separate GPT-6 Luna answer accuracy is **85.20%** (426/500).
These measure different paths. No statistically significant retrieval win is established.
Real local-agent continuation, physical ARM-board measurements and phone bindings
remain pending. Logical quotas do not cap total disk or process memory.

[Results and raw evidence](docs/performance.md) · [Evaluation policy](docs/evaluation-policy.md)

## Find your next step

- **Use it:** [documentation map](docs/README.md), [configuration](docs/configuration.md), [backups](docs/operations.md).
- **Build it:** [contributing](CONTRIBUTING.md), [repository maintenance](docs/repository.md), [architecture](docs/architecture.md), [security](SECURITY.md).
- **Improve it:** [cleanup and release plan](docs/project-plan.md), [roadmap](docs/roadmap.md).

Rust + Tokio + Axum + redb. MIT license.
[Website](https://instantkv.com) · [Changelog](CHANGELOG.md)
