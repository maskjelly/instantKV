# instantKV: source MVP for local-agent memory

This checkout adds structured memory to the existing Rust KV/checkpoint engine.
The MVP is unreleased. Keep user-facing explanations concise.

## What to evaluate

- `remember`, `recall`, `search`, `browse`, `forget`: content + topic/tags + event time + custom JSON metadata.
- Ordered time/topic/tag indexes; literal filtering plus bounded BM25 `search` with English stemming, not semantic search.
- All memory writes/deletes/expiry cleanup keep record/index changes in one redb transaction.
- Core can run in-process; HTTP/CLI/MCP add transports and scoped permissions.
- Local profile: loopback, private credentials, small cache, configurable quotas/query budgets.
- Native phone bindings/device tests and model-quality evaluation remain planned.

Start with [memory guide](docs/memory-mvp.md), [performance evidence and targets](docs/performance.md),
[roadmap](docs/roadmap.md). Read raw reports before quoting performance. Existing
browser KV replay is not the new retrieval benchmark. No cloud API or embedding
model is required by the memory service.

## Code map

- `crates/instantkv-core/src/memory.rs`: shape, indexes, query bounds and cursor contract.
- `crates/instantkv-core/src/search.rs`: transactional BM25 postings, corpus statistics, scoring budgets and ranked cursors.
- `crates/instantkv-core/src/store.rs`: record/index transactions, quota and expiry maintenance.
- `crates/instantkv/src/{server,client,mcp,main}.rs`: authenticated API, typed tools and CLI.
- `examples/memory.schema.json`: generated HTTP schemas.
- `examples/local-llm.py`: optional Ollama tool loop; reads actual MCP schemas.
- `crates/instantkv-core/examples/memory.rs`: embedded save/reopen/recall.
- `site/`: Astro, plain CSS, locally served Geist. Keep the minimal design.

## Verify changes

```sh
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked
python3 scripts/test-local-llm.py
cargo run -p instantkv-core --example memory -- /tmp/instantkv-agent-review
cd site
npm run check
npm test
npm run build
npm run verify
```

Socket tests need localhost permissions. No model is installed/downloaded by
these checks. Run `scripts/memory-bench.py` after a release build to reproduce
structured-memory measurements; run the Ollama example with an installed model
to evaluate real agent behavior. Do not call those two validations equivalent.

## Extension rules

Use app-defined metadata for additional fields. Keep candidate/output limits and
namespace grants; retrieval returning values requires both `list` and `get`.
Preserve conditional writes, TTL and checkpoint contracts. Tests must cover
index consistency after update/delete/expiry, recovery and cursor continuation.
Do not introduce cloud dependencies, automatic model calls, arbitrary uploaded
code execution or unsupported phone/performance claims.

## Documentation style

Use short, natural sentences based on ASD-STE100 principles. Full dictionary compliance is not required.
Keep the README brief. Put detailed procedures and limits in the guides.
Preserve exact API names, commands, benchmark conditions and source/release distinctions.
Follow the writing guidance in `CONTRIBUTING.md`.
