# Memory controller: first product milestone

Status: implementation contract, not shipped. Updated: 2026-10-09.
Audience: implementers. Product tasks live in [the roadmap](../roadmap.md).

## Outcome

A local agent remembers useful information across sessions, accepts corrections,
shows why it believes a fact, and honours forgetting. Installation and recovery
must be understandable without reading benchmark reports.

The Rust node stays model-free and unchanged during the evaluation campaign.
An optional Python standard-library controller uses the current HTTP API.
Local extraction uses an explicitly selected, already installed Ollama model.
No cloud model calls, downloads, paid evaluation calls or background inference.

## Decisions after reconsideration

- Build correction, provenance and forgetting before semantic retrieval.
- Keep model interpretation outside the storage node. Extraction proposes changes;
  deterministic validation and conditional writes apply them.
- Use one structured memory per entity/attribute within a scope. Current value,
  history, conflicts and retry receipts share one record/index transaction.
  There is no claim of atomic commits across multiple facts.
- Preserve actual evidence, not invented confidence scores. A source quote must
  come from the supplied user turn. Assistant statements are not user facts.
- Unclear changes stay unresolved. A model cannot silently replace a fact based
  only on lexical similarity, arrival order or a guessed entity identity.
- Build profiles from live records on demand. A cached summary must not resurrect
  a forgotten, superseded or expired value.
- Use existing BM25 for discovery. Controller filtering enforces live state.
  General graph reasoning, embeddings and connectors remain later tasks.

## Shared implementation contract

Place the package in `examples/memory_controller/`. This is an optional integration,
not an extension of the Rust API. Expose these imports from the package:

```python
from memory_controller import HTTPStore, MemoryController

store = HTTPStore(url, secrets_file)
controller = MemoryController(store, namespace="knowledge", scope="personal")
receipt = controller.apply(proposal)
profile = controller.profile(max_bytes=8192)
context = controller.context(query, max_bytes=8192)
detail = controller.inspect(entity, attribute)
receipt = controller.forget(entity, attribute, expected_revision=revision)
```

`HTTPStore` reads `INSTANTKV_APP_TOKEN` from the existing private credentials file.
It does not source a shell file. Require a loopback HTTP origin, no redirects,
timeouts and bounded responses. Let server permissions decide access. Never log
credentials or source text during errors.

An input proposal is a JSON object:

```json
{
  "entity": "user",
  "attribute": "response_style",
  "value": "short bullets",
  "kind": "preference",
  "operation": "assert",
  "source": {
    "id": "conversation-1/turn-1",
    "text": "Please use short bullets.",
    "role": "user",
    "occurred_at_ms": 1791504000000
  },
  "valid_until_ms": null
}
```

Kinds: `fact`, `preference`, `decision`, `event`. Operations: `assert`, `correct`.
`correct` requires `expected_revision` from inspection. A correction means an
explicit caller decision, not an extraction model's unrestricted permission.
Stable source IDs are supplied by the runtime; the extractor cannot invent them.

Public results are JSON objects. Receipts report `key`, `revision`, `status`.
Profile/context report `items` and `truncated`; each item includes provenance and
revision. Inspection exposes history and unresolved conflicts only to authorized
callers. Do not render memory content as executable instructions.

Use a stable hashed key for normalized scope/entity/attribute. Preserve scope and
slot identity in app-defined metadata for collision checks. Select a stable topic
derived from scope so profile pagination does not scan unrelated memories.

`assert` creates a new slot, recognizes an exact duplicate, or records a conflict.
Conflicted slots are excluded from default profile/context until an explicit
revision-protected correction resolves them. Distinguish a historical observation
from a correction: older event times cannot silently become current truth.

Retry the same source/operation without applying a change twice. Reusing a source
ID with a different payload is an error. Use bounded conflict retries; never
overwrite unconditionally after a revision conflict. A failed multi-fact ingest
reports each committed and rejected fact, so an identical retry can finish it.

Forget uses a revision-protected overwrite: remove values, quotes, history and
conflicts, and leave a small content-free tombstone. Default ingestion cannot
revive a forgotten slot. Explicit restoration is outside this milestone.
Do not retain whole transcripts in the controller or create a derived profile
copy. Physical erase from backups and intentional raw user writes are separate
operator concerns, not promises of this adapter.

Enforce the current metadata, content, query, candidate and output bounds before
writes. Bound history and retry receipts; fail clearly when full rather than
silently dropping provenance or replay protection. No unbounded JSON accumulation.
Semantic expiry uses `valid_until_ms`; controller reads exclude expired facts.
The native APIs remain general-purpose and do not enforce controller semantics.

## Extraction and agent experience

`extraction.py` exposes `extract_proposals(text, source_id, occurred_at_ms, model,
ollama_url="http://127.0.0.1:11434")`. It returns validated proposal objects.
Use constrained JSON output, input/output limits and a loopback-only Ollama client.
Reject invented source quotes, unknown fields and malformed output before writes.
Model failure leaves storage untouched. Extracted proposals default to `assert`.

`examples/local-memory-chat.py` provides one supported interactive harness.
It loads bounded profile/context before answering and offers opt-in capture with
review before application. It does not save assistant answers as facts.
Memory outages must be visible; answer-only mode can continue without claiming
memory is available. Neither commands nor traces leak credentials.

`python3 -m memory_controller` from `examples/` provides `apply`, `inspect`,
`profile`, `context`, `forget`, and optional `capture`. Supply JSON via stdin/file,
not awkward escaped shell strings. Shared options: `--url`, `--secrets-file`,
`--namespace`, `--scope`. Capture shows proposals unless explicitly applied.
CLI errors explain the next action and use a nonzero exit code.

## Acceptance and limits

One real-server scenario must cover create, retry, correction, conflict, restart,
profile/context, forgetting and replay rejection. A few focused tests should
cover concurrent conditional writes, extraction rejection and output budgets.
Use existing protocol/storage coverage rather than duplicating the Rust suite.
No model is installed or called by normal verification.

Document a runnable first-use path, read-only credential behaviour, model-down
behaviour, quota/history exhaustion and safe retry. Record what was actually run.
An installed-model trial is separate from fake-model and storage verification.

Rollout is optional and source-only. Stop the adapter to roll back; the native
node and existing memories remain usable. Managed records need explicit handling
before a future controller-format upgrade. Do not silently reinterpret versions.

Reevaluate after the vertical slice: usability friction, incorrect extraction,
stale answers, unresolved corrections, deletion failures, latency and resource
cost. Run product trials on separate development scenarios, not official final
benchmark questions.
