# Quick setup

Run the native binary beside your model. Storage and recall work offline once
installed. Rust 1.98+ is needed only for a source build; Docker is optional.

Want to see it first? The [browser demo](https://instantkv.com/demo/) writes real
records and lets you read them back, with no account or setup.

For shared knowledge and private agent namespaces, use `INSTANTKV_PROFILE=swarm` on the
first Docker setup or `instantkv init --profile swarm` in a fresh binary setup.
Follow [the local-agent guide](cloud-agents.md) for scopes and worker provisioning.
The examples below use the default local profile.

The structured-memory MVP is in this source checkout and is unreleased. Build
from this source for `remember`, `recall`, `browse` and `forget`; earlier archives
contain the original KV/checkpoint tools. [MVP guide](memory-mvp.md).

## Native binary first

From this checkout, with Rust 1.98+:

```sh
cargo install --path crates/instantkv --locked
mkdir my-local-memory
cd my-local-memory
instantkv init
instantkv serve
```

Or install the published source with
`cargo install --git https://github.com/maskjelly/instantKV --locked instantkv`.
Source installs need network access for dependencies once. After installation,
local storage and recall run offline.

In another terminal in the same directory:

```sh
instantkv remember "Prefer Rust for local tools" --topic preferences --tag local
instantkv recall --topic preferences --query Rust
instantkv browse --limit 10
instantkv doctor
```

`init` creates `instantkv.toml` and private, randomly generated credentials in
`.instantkv/credentials.env`. The default `local` profile uses smaller budgets
and binds to `127.0.0.1:8080`. The server and CLI read the credential file
automatically. Data stays in `.instantkv/data`; preserve that directory across
upgrades. Setup never overwrites existing files. Use `init --profile agent` for
the earlier larger quotas. [Local memory and ARM limits](local-first.md).

## Checksummed release binary

Published Linux x86_64 and Apple Silicon macOS archives need no compiler:

```sh
git clone https://github.com/maskjelly/instantKV.git
cd instantKV
./scripts/install.sh "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"
```

The installer verifies SHA-256. Linux ARM64 detection and packaging are implemented;
its archive must be built and published before downloads work. Use the native
source build above until then. [Platform status](local-first.md#arm-means-a-processor-family-not-one-operating-system).

## Docker is optional

```sh
git clone https://github.com/maskjelly/instantKV.git
cd instantKV
./scripts/quickstart.sh
./scripts/kv.sh put knowledge project/storage --value '{"content":"Use Rust + redb"}'
./scripts/kv.sh get knowledge project/storage
```

Docker defaults to the local profile too. The host port is loopback-only and the
database persists in a named volume. Set `INSTANTKV_PORT=8095` when 8080 is taken;
keep it set for later commands or save it in a private `.env`. Setup retains state.
On supported x86_64/ARM64 Docker hosts, it attempts the checksummed Linux archive
and falls back to source compilation if the archive is unavailable.
`INSTANTKV_BUILD_SOURCE=source-build` forces that path. Initial compilation and
image/release downloads need internet; the running local node does not.

## Run the demo without setup

```sh
instantkv demo
instantkv demo --swarm
```

The demo starts an isolated server, saves knowledge and a checkpoint over HTTP,
clears simulated agent context, kills the server process, restarts it, and verifies
the restored capsule and retained knowledge. Scratch memory must be gone. It
cleans up its child processes and temporary directory automatically.

## Save before compaction

```sh
curl -fsSL https://raw.githubusercontent.com/maskjelly/instantKV/main/examples/checkpoint.json -o checkpoint.json
instantkv checkpoint --file checkpoint.json
instantkv restore --agent builder --session project-1
```

In the cloned Docker project: `./scripts/kv.sh checkpoint < examples/checkpoint.json`.
Checkpoint accepts JSON from stdin by default; CLI file/stdin input is capped at 1 MiB.

Keep the returned checkpoint ID or agent/session locator in the agent runtime's
session metadata outside compacted prompt text. On the next checkpoint, include
the returned `latest_revision` as `expected_latest_revision`. Reusing an ID with
the same payload is idempotent; conflicting payloads and stale pointers fail.

## Benchmark your server

```sh
instantkv bench --namespace scratch --operation get --requests 5000 --concurrency 16
instantkv bench --namespace knowledge --operation put --requests 1000 --concurrency 8
```

The benchmark uses real HTTP keep-alive requests and reports successful throughput,
p50/p95/p99 latency, and error counts. Setup is excluded. Ordinary benchmark keys
are removed afterward. Checkpoint/restore benchmarks retain their snapshots and
should use an isolated disposable server/data directory. Recorded VPS results and
methodology are in [benchmarks](benchmarks.md).

## Remote server

Keep the server bound to loopback and use an SSH tunnel:

```sh
ssh -N -L 8080:127.0.0.1:8095 your-vps
```

Point the client at the tunnel and supply a credentials file obtained securely
from the server: `instantkv --secrets-file /private/path/credentials.env get knowledge key`.
Environment `INSTANTKV_TOKEN` overrides the client's saved credential; server
secrets use the environment names in TOML. Never put tokens in CLI arguments.

## Stop or upgrade

`docker compose stop` retains the volume. Start again with
`docker compose up -d --wait`. Before upgrading, follow the [offline backup procedure](operations.md).
Do not remove the named volume if you want to retain memory.
