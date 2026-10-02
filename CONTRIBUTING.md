# Contributing

Use Rust 1.98 or later. Container checks also need Docker Compose.
Keep changes focused and explain the resulting behavior.
For a large storage-format change, start with an issue.

```sh
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked
python3 scripts/test-local-llm.py
cargo build --workspace --release --locked
./target/release/instantkv demo
./target/release/instantkv demo --swarm
./target/release/instantkv check-config --config config/instantkv.example.toml
./target/release/instantkv check-config --config config/local-cache.toml
./target/release/instantkv check-config --config config/swarm.toml
./target/release/instantkv check-config --config config/local.toml
```

## Source map

- `crates/instantkv-core/src`: configuration, admission, clocks, tables, transactions.
- `crates/instantkv/src`: auth, HTTP, client, CLI, MCP, demo and benchmark.
- `crates/*/tests`: observable invariants and protocol behavior.
- `config`, `examples`, `docs`, `scripts`: setup, schemas and reproducible checks.

Test externally visible behavior and storage invariants. A regression test must fail with the old behavior.
Use a fake clock for deterministic expiry tests.
Do not weaken durability to improve benchmark results.
Never log tokens or stored memory.
Document format changes and migration steps before merging.

Generate the schemas from the Rust types:

```sh
cargo run --locked -p instantkv -- schema > examples/checkpoint.schema.json
cargo run --locked -p instantkv -- schema --kind memory > examples/memory.schema.json
```

Artwork tooling is optional and is not a build dependency.
To render with Tesseract 0.3.0, use `python3 scripts/render-design.py --tsrct /path/to/tsrct`.
[Asset sources and licenses](docs/assets/README.md).

Use a clear commit message.
Describe the problem, resulting behavior, validation and known limits in the pull request.
For deployment changes, run the [container setup](docs/quickstart.md).

## Website and documentation

Edit the Markdown guides to update website documentation.
For a new guide, add navigation in `site/src/lib/docs.ts`.
Site work needs Node 22.12 or later.
Run `npm ci`, `npm run check`, `npm test`, `npm run build` and `npm run verify` in `site/`.
Before deployment, verify mobile layout, search, copying and benchmark controls.
[Website operations](docs/website.md).

Benchmark claims must match committed raw reports, hardware, workload and source revision.
Keep measured results separate from unverified targets.
Native phone support, model-quality results, managed hosting and replicas remain planned.

## Writing style

Use ASD-STE100 principles with natural software terminology. Full dictionary compliance is not a project requirement.

- Keep most sentences below 25 words and instructions below 20 words.
- Use active voice, one topic per paragraph and one action per instruction.
- Use the same term for the same feature. Keep API and configuration names exact.
- Explain unfamiliar abbreviations at first use. Keep detailed contracts in the guides.
- Separate source-MVP features, released binaries, measurements and planned work.

The [official ASD-STE100 standard](https://www.asd-ste100.org/) provides the writing rules and controlled dictionary.
