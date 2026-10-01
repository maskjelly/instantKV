# Quick setup

Choose Docker Compose or Rust 1.98+.

## Docker: no Rust install needed

```sh
git clone https://github.com/maskjelly/instantKV.git
cd instantKV
./scripts/quickstart.sh
./scripts/kv.sh put knowledge project/storage --value '{"content":"Use Rust + redb"}'
./scripts/kv.sh get knowledge project/storage
```

The host port is loopback-only. Set `INSTANTKV_PORT=8095 ./scripts/quickstart.sh`
when 8080 is taken. Keep that variable set for later Compose commands, or put
`INSTANTKV_PORT=8095` in a private `.env` file. Re-running setup retains state.
On x86_64 Linux Docker hosts, setup downloads the checksummed release binary.
Other platforms, unavailable releases, or `INSTANTKV_BUILD_SOURCE=source-build`
use a source build; that initial compilation can take several minutes.

## Binary: no compiler needed on supported platforms

Linux x86_64 and Apple Silicon macOS:

```sh
git clone https://github.com/maskjelly/instantKV.git
cd instantKV
./scripts/install.sh "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"
instantkv init
instantkv serve
```

The installer checks the archive SHA-256 before installing. For other platforms,
or to compile from source, use Rust 1.98+:

```sh
cargo install --git https://github.com/maskjelly/instantKV --locked instantkv
instantkv init
instantkv serve
```

In another terminal in the same directory:

```sh
instantkv put knowledge project/storage --value '{"kind":"decision","content":"Use Rust + redb"}'
instantkv get knowledge project/storage
instantkv list knowledge --prefix project/
instantkv doctor
```

`init` creates `instantkv.toml` and private, randomly generated credentials in
`.instantkv/credentials.env`. The server and CLI read that file automatically;
there is no token-copy step. It never overwrites an existing setup. Data stays
in `.instantkv/data`; preserve that directory across upgrades.

## Run the demo without setup

```sh
instantkv demo
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
ssh -N -L 8080:127.0.0.1:8095 rove
```

Point the client at the tunnel and supply a credentials file obtained securely
from the server: `instantkv --secrets-file /private/path/credentials.env get knowledge key`.
Environment `INSTANTKV_TOKEN` overrides the client's saved credential; server
secrets use the environment names in TOML. Never put tokens in CLI arguments.

## Stop or upgrade

`docker compose stop` retains the volume. Start again with
`docker compose up -d --wait`. Before upgrading, follow the [offline backup procedure](operations.md).
Do not remove the named volume if you want to retain memory.
