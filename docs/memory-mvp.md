# Memory for local LLMs

Status: implemented in this source checkout, unreleased, 2026-10-03.
Build from source for these commands; earlier release archives do not include them.

Save facts, preferences, decisions and observations beside your model. Retrieve
them by topic, tag, event time or literal keywords. No model or embedding calls
are needed by the memory engine. Your runtime decides what to save and inserts
retrieved facts into the model's context.

## Four everyday tools

| CLI / MCP tool | Use |
|---|---|
| `remember` | Save content, topic, tags, optional event time and custom metadata |
| `recall` | Find memories using any combination of supported filters |
| `browse` | Page through permitted memories, newest event time first |
| `forget` | Explicitly delete one memory and its indexes |

The seven original KV/checkpoint MCP tools remain available. Structured memory
uses a durable JSON records namespace such as `knowledge`; RAM scratch remains
a separate raw KV cache. Existing ordinary records stay accessible through
`get`/`list`; they are not silently interpreted as structured memories.

## Try it locally

From the repository, with Rust 1.98+:

```sh
cargo install --path crates/instantkv --locked
mkdir my-local-memory
cd my-local-memory
instantkv init
instantkv serve
# Another terminal, same directory:
instantkv remember "Prefer Rust for local tools" \
  --key preferences/language --topic preferences --tag local \
  --metadata '{"source":"user","app":{"confidence":0.9}}'
instantkv recall --topic preferences --query Rust
instantkv browse --limit 10
```

`remember` returns a key and revision. Without `--key`, it generates a UUID key.
Using a stable key makes an uncertain save inspectable; repeating a create fails
with a conflict. Read its existing value/revision before retrying or updating:

```sh
instantkv get knowledge preferences/language
instantkv remember "Prefer Rust for embedded tools" \
  --key preferences/language --topic preferences --if-revision 1
instantkv forget preferences/language --if-revision 2
```

The revisions above are illustrative; use the actual returned revisions. Revision
counters belong to the namespace, so other writes can advance them.

## Topics, tags and time

Topics and tags are exact labels, trimmed and lowercased. A memory has one optional
topic and up to eight tags. Duplicate normalized tags are removed. Labels accept
1–64 UTF-8 bytes without control characters. Structured-memory keys accept at
most 256 bytes, even if the namespace allows larger raw KV keys. Content accepts up to 16 KiB;
custom metadata accepts an 8 KiB JSON object. Namespace value limits still apply
to the entire stored envelope.

Event time defaults to server time at each save. Supply `--occurred-at-ms` for an
older observation. `written_at_ms` reports when the server stored the version;
`occurred_at_ms` reports when the event happened. Updating without an explicit
event time gives the updated memory the current event time.

```sh
instantkv remember "Chose redb for the local app" \
  --key decisions/storage --topic decisions --tag local \
  --occurred-at-ms 1790985600000
instantkv recall --topic decisions --tag local \
  --since-ms 1790985600000 --until-ms 1791072000000
```

Times are Unix milliseconds and both endpoints are inclusive. The host runtime
converts natural-language dates such as "last week" using the user's timezone.
Results sort by event time descending, then key descending for ties.

## Keyword retrieval and pagination

`--query "Rust local"` requires both literal substrings in the content,
case-insensitively. Up to eight whitespace-separated terms / 256 bytes are
accepted. Metadata is stored and returned; the MVP does not search its fields.
This is not semantic similarity, relevance ranking or automatic fact extraction.

Time, topic and tag lookups use ordered indexes. Combined topic/tag filters use
the topic index and check the tag. Keywords filter those candidates; a keyword
query without a topic/tag uses the time index and may need several pages.

Defaults: 20 results, 16 KiB total serialized response. Limits: 1–100 results,
and a configured maximum of 64 KiB for the response. Scanning stops at 1,000
candidates or 4 MiB of encoded records per page. Configure those work caps in
`[memory]`; these are work/output budgets, not an RSS limit.

```sh
instantkv recall --topic decisions --limit 10 --max-bytes 16384
# Copy the returned next_cursor, then keep exactly the same filters:
instantkv recall --topic decisions --limit 10 --max-bytes 16384 \
  --cursor 'RETURNED_CURSOR'
```

Follow `next_cursor` until null, including empty pages. A cursor is bound to the
namespace and filters; changing them fails validation. Changing page size or
output budget is permitted. If a single matching memory does not fit, increase
`max_bytes`; the API does not silently truncate the memory. Pages are not a
stable snapshot across writes: edits/new events can move records between pages.

## HTTP and MCP

Routes under `/v1/namespaces/{namespace}`:

| Method / route | Body / result | Required grants |
|---|---|---|
| `POST /memories` | `{key?, memory: {content, topic?, tags?, metadata?, occurred_at_ms?}, ttl_seconds?, if_revision?}` → saved memory | put |
| `GET /memories` | Query filters → `{items, next_cursor, scanned, scanned_bytes}` | list + get |
| `GET /memories/{key}` | Exact structured memory, revision and timestamps | get |
| `DELETE /memories/{key}` | Forget; optional `If-Match: "revision"` | delete |

Creates are conditional: omit `if_revision` to require an absent key, or supply
the observed positive revision to update. `if_revision` requires a key. TTL uses
the namespace's existing policy. Forget refuses raw KV records.

The MCP `remember` tool accepts the memory fields directly, without the HTTP
`memory` wrapper. `recall`/`browse` accept the query fields directly. Credentials,
request limits and namespace scopes apply exactly as for the original API.
[MCP setup](agents.md). [Generated HTTP schemas](../examples/memory.schema.json)
come from `instantkv schema --kind memory`.

## Connect an actual local model

For a quick isolated integrity demo without a model or manual server setup:

```sh
cargo build --release --locked -p instantkv
python3 scripts/memory-bench.py --records 100 --runs 1 --queries 10 \
  --output /tmp/instantkv-memory-demo.json
```

It starts a temporary server, saves structured memories, checks topic/tag/time
queries, kills/restarts the server, verifies complete saved receipts and calls
the actual MCP bridge. It cleans up its own state. This checks infrastructure;
use the model example below to evaluate real inference behavior.

The [Ollama example](../examples/local-llm.py) reads the four tool schemas directly
from the running instantKV MCP adapter and forwards real tool calls/results.
It uses Python's standard library. Start instantKV and Ollama with an already
installed tool-capable model, then run from your memory directory:

```sh
python3 /absolute/path/to/instantKV/examples/local-llm.py \
  --model YOUR_INSTALLED_MODEL --trace \
  --prompt "Remember that I prefer Rust for local tools. Use topic preferences."
# Start a fresh invocation, with no previous chat messages:
python3 /absolute/path/to/instantKV/examples/local-llm.py \
  --model YOUR_INSTALLED_MODEL --trace \
  --prompt "What language do I prefer for local tools? Check memory first."
```

Only tool names are traced. The model's ability to call tools varies; evaluate
the model you ship. Actual HTTP/MCP tools and the example's tool-loop contract
are tested, including the example's MCP bridge against a real local server.
No installed Ollama model was available for a real inference run
during this implementation. This example is an integration entry point, not
evidence of model recall quality or phone support. The protocol follows
[Ollama's tool-calling API](https://docs.ollama.com/capabilities/tool-calling).

## Embed and extend

The [Rust example](../crates/instantkv-core/examples/memory.rs) saves, closes the
engine and recalls from a new engine instance. No HTTP or async runtime:

```sh
cargo run -p instantkv-core --example memory -- /tmp/instantkv-embedded-memory
```

An app chooses its own namespace, budgets and metadata. The embedding app owns
authorization, cleanup scheduling and the data path; run synchronous storage
off the UI thread. Swift/Kotlin bindings and device lifecycle tests are planned.
Agents can store their own fields in metadata and integrate through typed tools;
the memory service does not execute arbitrary uploaded plugins.

## Storage and upgrade boundary

Structured records use the reserved `_instantkv_memory: 1` JSON envelope and
the existing `records_v1` table. The additive `memory_index_v1` table contains
time, topic and tag entries pointing to those records. Writes, updates, deletes
and expiry cleanup maintain records/indexes in the same immediate transaction.
Raw KV puts replacing a structured record also remove its previous indexes.

Old ordinary records need no conversion. Use `remember` to create indexed versions
deliberately. Back up existing data offline before trying this unreleased build.
Older binaries do not maintain these indexes; do not reopen an MVP database with
an older writer. To downgrade, restore a pre-MVP backup. Logical quotas include
the full memory JSON envelope but exclude physical indexes/database overhead.

## Evidence and next steps

The [performance plan](performance.md) separates the new 10,000-memory Mac
measurements from engineering targets and device tests still needed.
The [roadmap](roadmap.md) prioritizes real local-model evaluations, native mobile
integration, portable exports and optional richer retrieval.
