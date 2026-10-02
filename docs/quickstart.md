# Quick setup

Run the native binary beside your model. Storage and retrieval work offline after installation.
A source build needs Rust 1.98 or later. Docker is optional.

The [browser demo](https://instantkv.com/demo/) needs no account.
Live mode saves, recalls, browses and deletes structured memories on the Rust server.
Recorded mode shows saved responses from fresh memory runs.

For a fresh swarm setup, use `instantkv init --profile swarm` or `INSTANTKV_PROFILE=swarm` with Docker.
The examples below use the default local profile.
[Shared and private agent setup](cloud-agents.md).

The structured-memory MVP is implemented in source and remains unreleased.
Build from this checkout for `remember`, `recall`, `browse` and `forget`.
Earlier archives contain the original KV and checkpoint tools.
[MVP guide](memory-mvp.md).

## Native binary first

From this checkout, with Rust 1.98+:

```sh
cargo install --path crates/instantkv --locked
mkdir my-local-memory
cd my-local-memory
instantkv init
instantkv serve
```

To install directly from GitHub, run:
`cargo install --git https://github.com/maskjelly/instantKV --locked instantkv`.

Source installation can download dependencies. Local storage and retrieval run offline afterward.

In another terminal in the same directory:

```sh
instantkv remember "Prefer Rust for local tools" --topic preferences --tag local
instantkv recall --topic preferences --query Rust
instantkv browse --limit 10
instantkv doctor
```

`init` creates `instantkv.toml` and private credentials in `.instantkv/credentials.env`.
The server and CLI load that credentials file automatically.
The default local profile uses smaller limits and listens on `127.0.0.1:8080`.
Data remains in `.instantkv/data`; keep this directory across upgrades.
Setup does not overwrite existing files.

Use `init --profile agent` for larger quotas.
[Local memory and device support](local-first.md).

## Checksummed release binary

Published Linux x86_64 and Apple Silicon macOS archives need no compiler:

```sh
git clone https://github.com/maskjelly/instantKV.git
cd instantKV
./scripts/install.sh "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"
```

The installer verifies SHA-256 checksums.
Linux ARM64 CI and packaging passed, but its archive has not been published in a release.
Earlier release binaries do not contain the structured-memory MVP.
For the new tools, use the source build above.
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

## Run the demo without setup

```sh
instantkv demo
instantkv demo --swarm
```

The demo starts an isolated server and saves knowledge and a checkpoint through HTTP.
It clears simulated context, terminates the server and restarts it.
It verifies the restored capsule, retained knowledge and empty scratch cache.
The demo removes its child processes and temporary directory.

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
