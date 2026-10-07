# Quick setup

Run the native binary beside your model. Storage and retrieval work offline after installation.
A source build needs Rust 1.98 or later. Docker is optional.

Use the [full benchmark results](benchmarks/2026-10-04-full-retrieval/README.md)
to inspect retrieval evidence. Follow this guide to run your own memory service.

For a fresh swarm setup, use `instantkv init --profile swarm` or `INSTANTKV_PROFILE=swarm` with Docker.
The examples below use the default local profile.
[Shared and private agent setup](cloud-agents.md).

The structured-memory MVP is implemented in source and remains unreleased.
Build from this checkout for `remember`, `recall`, `search`, `browse` and `forget`.
Earlier archives contain the original KV and checkpoint tools.
[MVP guide](memory-mvp.md).

## Native binary first

From this checkout, with Rust 1.98+:

```sh
cargo install --path crates/instantkv --locked
instantkv start --dir my-local-memory
```

To install directly from GitHub, run:
`cargo install --git https://github.com/maskjelly/instantKV --locked instantkv`.

Source installation can download dependencies. Local storage and retrieval run offline afterward.

In another terminal:

```sh
cd my-local-memory
instantkv remember "Prefer Rust for local tools" --topic preferences --tag local
instantkv recall --topic preferences --query Rust
instantkv search "preferred language for local tooling"
instantkv browse --limit 10
instantkv doctor
```

`start` creates the directory, `instantkv.toml` and private credentials in
`.instantkv/credentials.env` on first use. Later starts reuse them.
The server and CLI load that credentials file automatically.
The default local profile uses smaller limits and listens on `127.0.0.1:8080`.
Data remains in `.instantkv/data`; keep this directory across upgrades.
Setup does not overwrite existing files. Use `instantkv init` and `instantkv serve`
when you need to review or edit configuration before starting the server.

Use `init --profile agent` for larger quotas.
[Local memory and device support](local-first.md).

Published binaries contain only the earlier KV and checkpoint tools.
Use the source build above for structured memory.
[Platform status](local-first.md#arm-means-a-processor-family-not-one-operating-system).

## Docker is optional

```sh
git clone https://github.com/maskjelly/instantKV.git
cd instantKV
INSTANTKV_BUILD_SOURCE=source-build ./scripts/quickstart.sh
./scripts/kv.sh put knowledge project/storage --value '{"content":"Use Rust + redb"}'
./scripts/kv.sh get knowledge project/storage
```

Docker uses the local profile and a loopback host port. Data persists in a named volume.
If port 8080 is in use, set `INSTANTKV_PORT=8095`.
Keep that setting for later commands, or save it in a private `.env` file.

On supported x86_64/ARM64 hosts, setup first tries the published Linux archive.
It compiles from source if that archive is unavailable.
To use the current MVP, force a source build with `INSTANTKV_BUILD_SOURCE=source-build ./scripts/quickstart.sh`.

Initial builds and downloads need internet access. The running local node does not.

## Save before compaction

```sh
curl -fsSL https://raw.githubusercontent.com/maskjelly/instantKV/main/examples/checkpoint.json -o checkpoint.json
instantkv checkpoint --file checkpoint.json
instantkv restore --agent builder --session project-1
```

For Docker, run `./scripts/kv.sh checkpoint < examples/checkpoint.json`.
Checkpoint input can come from stdin or a file. The CLI input limit is 1 MiB.

Keep the returned checkpoint locator in runtime session metadata outside the prompt.
For the next checkpoint, supply the returned `latest_revision` as `expected_latest_revision`.
Identical ID/payload retries are idempotent: they do not create a second checkpoint.
Conflicting payloads and stale latest-pointer revisions fail.

## Benchmark your server

```sh
instantkv bench --namespace scratch --operation get --requests 5000 --concurrency 16
instantkv bench --namespace knowledge --operation put --requests 1000 --concurrency 8
```

The benchmark uses real HTTP requests with keep-alive.
It reports successful throughput, p50/p95/p99 latency and errors.
Timing excludes setup. Ordinary benchmark keys are removed afterward.

Use an isolated server for checkpoint and restore benchmarks. Those benchmarks retain checkpoint records.
[Recorded results and methodology](benchmarks.md).

## Remote server

Keep the server bound to loopback and use an SSH tunnel:

```sh
ssh -N -L 8080:127.0.0.1:8095 your-vps
```

Set the client credentials with `--secrets-file /private/path/credentials.env`.
Get the file securely from the server.
Never pass tokens as CLI arguments.

`INSTANTKV_TOKEN` overrides the saved client credential.
Server credentials use the environment names in TOML.

## Stop or upgrade

`docker compose stop` retains the volume.
To start again, run `docker compose up -d --wait`.
Before an upgrade, follow the [backup procedure](operations.md).
Keep the named volume to retain memory.
