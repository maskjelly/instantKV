# CLI reference

These examples use the installed binary and default local profile.
For Docker, substitute `./scripts/kv.sh` for `instantkv`.
For swarms, pass `alpha`, `beta` or `shared` explicitly.
Use `--namespace alpha_checkpoints` for Alpha checkpoints.
Run `instantkv COMMAND --help` for the current option list.

## Structured memory — source MVP

Build the current checkout for these unreleased commands:

```sh
instantkv remember "Prefer Rust for local tools" --topic preferences --tag local
instantkv recall --topic preferences --query Rust
instantkv search "preferred language for local tooling" --limit 10
instantkv browse --limit 10
instantkv forget RETURNED_KEY
instantkv schema --kind memory
```

`remember` accepts `--key`, `--namespace`, `--topic`, repeated `--tag`,
`--metadata` (JSON object), `--occurred-at-ms`, `--ttl`, and `--if-revision`.
New keys are create-only. Updating requires a stable key and its observed revision.
`forget --if-revision N` protects against deleting another update.

`recall` and `browse` accept `--namespace`, `--topic`, `--tag`, `--query`,
`--since-ms`, `--until-ms`, `--limit`, `--max-bytes`, and `--cursor`. Times are
inclusive Unix milliseconds. All keyword terms must occur in content,
case-insensitively. Use the same filters with each cursor, including empty pages.
[Shapes, integration example and limits](memory-mvp.md).

`search QUERY` ranks content with BM25 and English stemming. It accepts the same
label/time/page options; supply query text as a positional argument, without `--query`.
Use `--expand` for the optional small English synonym list. Repeat
`--expansion-term WORD` for app-defined related words. Both are bounded to eight
added terms. Check `query_reduced` and `truncated`. Managed writes invalidate ranked cursors.

## Connection and credentials

| Global option    | Default                      |
| ---------------- | ---------------------------- |
| `--url`          | `http://127.0.0.1:8080`      |
| `--secrets-file` | `.instantkv/credentials.env` |

`INSTANTKV_TOKEN` overrides the saved app credential. The CLI does not accept a token argument.
Run setup commands in the directory that contains the generated configuration.

```sh
instantkv --url http://127.0.0.1:8095 --secrets-file /private/credentials.env get knowledge project/stack
```

## Setup and diagnostics

| Command                                                    | Behavior                                                           |
| ---------------------------------------------------------- | ------------------------------------------------------------------ |
| `init [--dir PATH] [--profile local\|agent\|swarm]`        | Creates config and unique private credentials; refuses overwrites  |
| `serve [--config PATH] [--bind IP:PORT] [--data-dir PATH]` | Runs the server; validates configuration and credentials           |
| `check-config --config PATH`                               | Validates TOML policies without opening storage or reading secrets |
| `doctor [--config PATH] [--offline]`                       | Checks setup and live health; offline skips server connectivity    |
| `schema`                                                   | Prints the checkpoint JSON Schema generated from Rust types        |

## Records

```sh
instantkv put knowledge project/stack --value '{"content":"Rust + redb"}' --if-absent
instantkv get knowledge project/stack
instantkv list knowledge --prefix project/ --limit 100
instantkv stats knowledge
instantkv put scratch run/note --value '{"content":"temporary"}' --ttl 60
```

`put` accepts `--value`, `--file PATH` or stdin. It reports the new revision.
`get` writes the original bytes to stdout and the revision to stderr.

For an update, supply the observed revision with `put --if-revision REVISION`.
Do not combine `--if-absent` and `--if-revision`.

`list` returns metadata pages and an optional continuation cursor.
Pass that cursor with `--cursor CURSOR`. Pages do not form a stable snapshot across writes.
`delete NAMESPACE KEY [--if-revision REVISION]` removes a record.

## Checkpoints and restore

```sh
instantkv checkpoint --file examples/checkpoint.json
# JSON from stdin is also accepted:
instantkv checkpoint < examples/checkpoint.json
instantkv restore --agent builder --session project-1 --max-bytes 32768
instantkv restore --id first-checkpoint
```

The CLI checkpoint input limit is 1 MiB; the server can impose a smaller body limit.
Save, restore and delete-checkpoint default to namespace `checkpoints`.
Restore requires either `--id`, or both `--agent` and `--session`.
Its response budget accepts 512 bytes to 1 MiB. A response that exceeds the budget fails.

Use a unique ID and observed `expected_latest_revision` for each new checkpoint.
Never reuse a deleted checkpoint ID.

`delete-checkpoint ID` removes an old bundle and frees its logical quota.
The latest checkpoint is protected until a newer checkpoint advances the pointer.
[Checkpoint schema and behavior](agent-memory.md).

## MCP and demos

`instantkv mcp` provides twelve source-MVP tools over stdin/stdout.
It connects to the running HTTP server. Diagnostics use stderr.
[Agent setup](agents.md).

`instantkv demo` and `instantkv demo --swarm` create temporary instances and verify them through real HTTP.
They remove their processes and temporary state afterward.

## Benchmark

```sh
instantkv bench --namespace knowledge --operation get --requests 5000 --concurrency 16 --value-bytes 512 --output results.json
```

Benchmark operations are `get`, `put`, `checkpoint` and `restore`.
Use a checkpoint namespace in a disposable instance for the last two.
Requests, concurrency and values must fit the configured limits.
Timing excludes setup. Ordinary keys are removed afterward; checkpoint records remain.
[Methodology and suite](benchmarks.md).
