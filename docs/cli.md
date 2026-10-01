# CLI reference

Examples use a locally installed `instantkv` and the default single-agent profile.
For Docker use `./scripts/kv.sh` in its place. For swarm calls pass `alpha`, `beta`
or `shared` explicitly, and `--namespace alpha_checkpoints` for Alpha handoffs.
Run `instantkv COMMAND --help` for the authoritative option list.

## Connection and credentials

Global flags: `--url` defaults to `http://127.0.0.1:8080`;
`--secrets-file` defaults to `.instantkv/credentials.env`. Environment
`INSTANTKV_TOKEN` overrides the saved app credential. The CLI never accepts a token
argument. Run local setup commands from the directory containing the generated files.

```sh
instantkv --url http://127.0.0.1:8095 --secrets-file /private/credentials.env get knowledge project/stack
```

## Setup and diagnostics

| Command | Behavior |
|---|---|
| `init [--dir PATH] [--profile agent\|swarm]` | Creates config and unique private credentials; refuses overwrites |
| `serve [--config PATH] [--bind IP:PORT] [--data-dir PATH]` | Runs the server; validates configuration and credentials |
| `check-config --config PATH` | Validates TOML policies without opening storage or reading secrets |
| `doctor [--config PATH] [--offline]` | Checks setup and live health; offline skips server connectivity |
| `schema` | Prints the checkpoint JSON Schema generated from Rust types |

## Records

```sh
instantkv put knowledge project/stack --value '{"content":"Rust + redb"}' --if-absent
instantkv get knowledge project/stack
instantkv list knowledge --prefix project/ --limit 100
instantkv stats knowledge
instantkv put scratch run/note --value '{"content":"temporary"}' --ttl 60
```

`put` accepts `--value`, `--file PATH`, or stdin; it reports the new revision.
`get` writes original value bytes to stdout and the revision to stderr. To update
safely, supply the actual observed revision with `put --if-revision REVISION`.
`--if-absent` and `--if-revision` are mutually exclusive.

`list` returns bounded metadata with an optional continuation cursor. Pass that
cursor with `--cursor CURSOR`; pages do not promise a snapshot during concurrent
writes. `delete NAMESPACE KEY [--if-revision REVISION]` explicitly forgets a record.

## Checkpoints and restore

```sh
instantkv checkpoint --file examples/checkpoint.json
# JSON from stdin is also accepted:
instantkv checkpoint < examples/checkpoint.json
instantkv restore --agent builder --session project-1 --max-bytes 32768
instantkv restore --id first-checkpoint
```

Checkpoint input is capped at 1 MiB. `--namespace` defaults to `checkpoints` on
save, restore and delete-checkpoint. Choose either `--id` or both `--agent` and
`--session` for restore. Byte budgets range from 512 bytes to 1 MiB; a response
that cannot fit is rejected. Save newer handoffs with unique IDs and the observed
`expected_latest_revision`; don't recycle deleted IDs.

`delete-checkpoint ID` reclaims an old capsule; deleting the current latest is
rejected until a newer checkpoint advances the pointer.
See [the complete schema and semantics](agent-memory.md).

## MCP and demos

`instantkv mcp` serves seven MCP tools over stdin/stdout and connects to your
running HTTP node. Diagnostics stay on stderr. See [agent setup](agents.md).
`instantkv demo` and `instantkv demo --swarm` create isolated temporary instances,
verify behavior over real HTTP and clean up after themselves.

## Benchmark

```sh
instantkv bench --namespace knowledge --operation get --requests 5000 --concurrency 16 --value-bytes 512 --output results.json
```

Operations: `get`, `put`, `checkpoint`, `restore`. For the latter two choose a
checkpoint namespace in a disposable instance. Request/concurrency/value limits
must fit its configured policies. Setup is excluded, ordinary keys are cleaned
up, and checkpoint records remain. See [methodology and full suite](benchmarks.md).
