# Contributing

Use Rust 1.98+ and Docker Compose for container checks. Keep changes focused and
explain the behavior they fix; use an issue for a larger storage-format proposal.

```sh
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked
cargo build --workspace --release --locked
./target/release/instantkv demo
./target/release/instantkv check-config --config config/instantkv.example.toml
./target/release/instantkv check-config --config config/local-cache.toml
```

## Source map

- `crates/instantkv-core/src`: configuration, admission, clocks, tables, transactions.
- `crates/instantkv/src`: auth, HTTP, client, CLI, MCP, demo and benchmark.
- `crates/*/tests`: observable invariants and protocol behavior.
- `config`, `examples`, `docs`, `scripts`: setup, schemas and reproducible checks.

Test invariants rather than duplicating implementation. A regression should show
why the old behavior fails. Keep fake-clock expiry tests deterministic. Never
weaken durability to improve benchmark numbers or print tokens/memory in logs.
Document storage-format changes and migrations before merging them.

Checkpoint schema is generated from Rust types:

```sh
cargo run --locked -p instantkv -- schema > examples/checkpoint.schema.json
```

Artwork is optional tooling, not a build dependency. To regenerate with Tesseract
0.3.0, use `python3 scripts/render-design.py --tsrct /path/to/tsrct`; see the
[asset licenses and sources](docs/assets/README.md).

Use a clear commit message (`feat`, `fix`, `docs`, `test`, `chore`); a PR should
state the problem, resulting behavior, validation and any material limitation.
Run [container quick-start](docs/quickstart.md) for deployment changes.
