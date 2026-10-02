# Memory for local LLMs

Status: source MVP, unreleased. Updated: 2026-10-03.

Build from this checkout to use these commands. Earlier release archives do not contain them.

instantKV stores facts, preferences, decisions and observations beside your model.
Queries can select a topic, tag, event time or literal keywords.
The memory engine requires no model or embedding calls.
Your runtime selects what to save and adds retrieved facts to the model context.

## Four everyday tools

| CLI / MCP tool | Use                                                                |
| -------------- | ------------------------------------------------------------------ |
| `remember`     | Save content, topic, tags, optional event time and custom metadata |
| `recall`       | Find memories using any combination of supported filters           |
| `browse`       | Page through permitted memories, newest event time first           |
| `forget`       | Explicitly delete one memory and its indexes                       |

The seven original KV and checkpoint MCP tools remain available.
Structured memory uses a durable JSON namespace, such as `knowledge`.
RAM scratch remains a separate raw KV cache.
The `get` and `list` operations still provide access to ordinary records.
Ordinary records do not become structured memories automatically.

## Try it locally

Run these commands from the repository. You need Rust 1.98 or later.

Run the commands after `instantkv serve` in another terminal, in the same memory directory.

```sh
cargo install --path crates/instantkv --locked
mkdir my-local-memory
cd my-local-memory
instantkv init
instantkv serve
```

In another terminal, in the same directory:

```sh
instantkv remember "Prefer Rust for local tools" \
  --key preferences/language --topic preferences --tag local \
  --metadata '{"source":"user","app":{"confidence":0.9}}'
instantkv recall --topic preferences --query Rust
instantkv browse --limit 10
```

`remember` returns a key and revision. If you omit `--key`, the server generates a UUID key.
A stable key lets you inspect the result after an uncertain save.
A repeated creation request fails if that key already exists.

Before you retry or update, read the saved value and revision:

```sh
instantkv get knowledge preferences/language
instantkv remember "Prefer Rust for embedded tools" \
  --key preferences/language --topic preferences --if-revision 1
instantkv forget preferences/language --if-revision 2
```

The revisions above are examples. Use the revisions from your responses.
Other writes in the same namespace can advance its revision counter.

## Topics, tags and time

Topics and tags are exact labels. The server removes outer spaces and converts the labels to lowercase.
Each memory can have one topic and up to eight tags.
The server removes duplicate normalized tags.

| Field                 | Limit                                             |
| --------------------- | ------------------------------------------------- |
| Topic or tag          | 1–64 UTF-8 bytes; no control characters           |
| Structured-memory key | 256 bytes, even if the raw KV key limit is larger |
| Content               | 16 KiB                                            |
| Custom metadata       | 8 KiB JSON object                                 |

The namespace value limit applies to the complete stored JSON envelope.

Each save uses the current server time as its default event time.
`written_at_ms` records when the server saved that version.
`occurred_at_ms` records when the event happened.
An update without an explicit event time uses the current server time.

For an older event, supply `--occurred-at-ms`:

```sh
instantkv remember "Chose redb for the local app" \
  --key decisions/storage --topic decisions --tag local \
  --occurred-at-ms 1790985600000
instantkv recall --topic decisions --tag local \
  --since-ms 1790985600000 --until-ms 1791072000000
```

Times use Unix milliseconds. Both time-range endpoints are inclusive.
The host runtime must convert phrases such as "last week" with the user's timezone.
Results have descending event-time order. Equal times have descending key order.

## Keyword retrieval and pagination

`--query "Rust local"` requires both literal substrings in the content.
Matching ignores letter case. A query accepts at most eight terms and 256 bytes.
Whitespace separates the terms.
The MVP returns metadata but does not search its fields.
It does not provide semantic similarity, relevance ranking or automatic fact extraction.

Time, topic and tag queries use ordered indexes.
A combined topic/tag query uses the topic index, then tests the tag.
Keyword filters test the candidate content.
A keyword query without a topic or tag uses the time index.
It can require several pages.

| Query setting              | Default or limit                          |
| -------------------------- | ----------------------------------------- |
| Results per page           | Default 20; range 1–100                   |
| Complete response size     | Default 16 KiB; configured maximum 64 KiB |
| Candidate records examined | At most 1,000 per page by default         |
| Encoded records examined   | At most 4 MiB per page by default         |

Set the scan and response limits in `[memory]`.
These limits do not cap the process RSS.

```sh
instantkv recall --topic decisions --limit 10 --max-bytes 16384
# Copy the returned next_cursor, then keep exactly the same filters:
instantkv recall --topic decisions --limit 10 --max-bytes 16384 \
  --cursor 'RETURNED_CURSOR'
```

1. Keep the namespace and filters unchanged.
2. Supply the returned `next_cursor`, even after an empty page.
3. Continue until `next_cursor` is null.

You can change the page size or response budget.
If one matching memory exceeds the budget, increase `max_bytes`.
The API returns an error instead of a partial memory.
Pages do not form a stable snapshot across writes.
Updates and new events can move records between pages.

## HTTP and MCP

Routes under `/v1/namespaces/{namespace}`:

| Method / route           | Body / result                                                                                                     | Required grants |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------- | --------------- |
| `POST /memories`         | `{key?, memory: {content, topic?, tags?, metadata?, occurred_at_ms?}, ttl_seconds?, if_revision?}` → saved memory | put             |
| `GET /memories`          | Query filters → `{items, next_cursor, scanned, scanned_bytes}`                                                    | list + get      |
| `GET /memories/{key}`    | Exact structured memory, revision and timestamps                                                                  | get             |
| `DELETE /memories/{key}` | Forget; optional `If-Match: "revision"`                                                                           | delete          |

If you omit `if_revision`, the key must not exist.
To update a memory, supply its key and the observed positive revision.
TTL follows the namespace policy.
The `forget` operation rejects raw KV records.

The MCP `remember` tool accepts memory fields directly. It does not use the HTTP `memory` wrapper.
The `recall` and `browse` tools accept query fields directly.
Credentials, request limits and namespace permissions apply to each call.

[MCP setup](agents.md).
The command `instantkv schema --kind memory` generates the [HTTP schemas](../examples/memory.schema.json).

## Connect an actual local model

Run this isolated storage test without a model:

```sh
cargo build --release --locked -p instantkv
python3 scripts/memory-bench.py --records 100 --runs 1 --queries 10 \
  --output /tmp/instantkv-memory-demo.json
```

The script starts a temporary server and saves structured memories.
It tests topic, tag and time queries.
Then it terminates and restarts the server.
It verifies every saved field and calls the actual MCP bridge.
It removes its temporary state.

This test verifies storage and transport. The model example below tests inference behavior.

The [Ollama example](../examples/local-llm.py) reads four tool schemas from the instantKV MCP adapter.
It sends tool calls and results between the model and adapter.
It uses the Python standard library.

1. Start instantKV.
2. Start Ollama with an installed model that supports tools.
3. Run the example from your memory directory:

```sh
python3 /absolute/path/to/instantKV/examples/local-llm.py \
  --model YOUR_INSTALLED_MODEL --trace \
  --prompt "Remember that I prefer Rust for local tools. Use topic preferences."
# Start a fresh invocation, with no previous chat messages:
python3 /absolute/path/to/instantKV/examples/local-llm.py \
  --model YOUR_INSTALLED_MODEL --trace \
  --prompt "What language do I prefer for local tools? Check memory first."
```

Trace output contains only tool names. Tool-call behavior depends on the model.
The HTTP/MCP tools and the example's protocol contract have automated tests.
The example's MCP bridge also passed a test with a real local server.

No installed Ollama model was available during implementation.
Model recall quality and phone support remain unverified.
The example follows [Ollama's tool-calling API](https://docs.ollama.com/capabilities/tool-calling).

## Embed and extend

The [Rust example](../crates/instantkv-core/examples/memory.rs) saves a memory and closes the engine.
A new engine instance retrieves that memory.
The example requires no HTTP server or asynchronous runtime.

```sh
cargo run -p instantkv-core --example memory -- /tmp/instantkv-embedded-memory
```

The app selects namespaces, limits and custom metadata.
The app controls authorization, cleanup scheduling and the data path.

Run synchronous storage calls outside the UI thread.

Swift/Kotlin bindings and device lifecycle tests are planned.
Agents can add metadata fields and connect through typed tools.
The service does not execute uploaded plugins.

## Storage and upgrade boundary

Structured records use the reserved `_instantkv_memory: 1` JSON envelope in `records_v1`.
The additional `memory_index_v1` table contains time, topic and tag entries.
Each entry points to a structured record.
Writes, updates, deletes and expiry cleanup change records and indexes in the same immediate transaction.
A raw KV write that replaces a structured record also removes the old index entries.

Ordinary records need no conversion.

1. Back up existing data offline before you use this unreleased build.
2. Use `remember` to create indexed memories when needed.

Older binaries do not maintain the new indexes.
Do not use an older writer with an MVP database.
To downgrade, restore a backup from before the MVP upgrade.

Logical quotas count the full JSON envelope. They exclude physical index and database overhead.

## Evidence and next steps

The [performance plan](performance.md) separates Mac measurements from device targets.
The [roadmap](roadmap.md) defines local-model evaluation, native mobile integration and portable exports.
Richer retrieval remains optional future work.
