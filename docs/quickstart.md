# First memory in a minute

Install Rust, then build/install the binary:

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
instantkv checkpoint --file examples/checkpoint.json
instantkv restore --agent builder --session project-1
```

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
should use an isolated disposable server/data directory.

## Remote server

Keep the server bound to loopback and use an SSH tunnel:

```sh
ssh -N -L 8080:127.0.0.1:8095 rove
```

Point the client at the tunnel and supply a credentials file obtained securely
from the server: `instantkv --secrets-file /private/path/credentials.env get knowledge key`.
Environment `INSTANTKV_TOKEN` overrides the client's saved credential; server
secrets use the environment names in TOML. Never put tokens in CLI arguments.
