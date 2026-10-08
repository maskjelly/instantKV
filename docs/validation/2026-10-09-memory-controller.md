# Memory controller validation

Date: 2026-10-09. Scope: optional source-only Python integration and its guide.
The Rust engine, HTTP contract and published benchmark reports are unchanged.
This record describes local checks, not CI, a release or a deployment.

## Implementation

Three isolated implementation threads supplied committed work:

- Lifecycle and bounded HTTP adapter: `2be36cc`, integrated as `18e8fed`.
- Reviewed local extraction and current-turn chat: `5c00f47`, integrated as `f8a7fb5`.
- CLI, first-use guide and restart scenario: `9c7b366`, integrated as `c5bb804`.

The integration branch is `codex/memory-product`. Planning commits are
`08979f9` and `32e8524`. The integration commit containing this record also
registers the guide on the site and adds the checks to the verification entry point.

## Passed checks

- `cargo build --locked -p instantkv`: built the current node for the scenario.
- `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets --locked -- -D warnings`
  and `cargo test --workspace --locked`: pass, including all 54 existing integration tests.
- `cargo run -p instantkv-core --example memory -- TEMP_DIR`: embedded save,
  reopen, search, recall, browse and revision-checked forgetting pass in isolated state.
- `python3 scripts/test-memory-controller.py`: five focused scenarios for lifecycle,
  freshness, finite capacity, concurrency, uncertain writes, pagination, budgets,
  TTL rejection and HTTP failures/permissions.
- `python3 scripts/test-memory-extraction.py`: six scenarios for caller provenance,
  malformed/oversized model output, known cloud-backed model rejection, redirects,
  time limits, review boundaries and honest failures. These use a fake local model.
- `python3 scripts/test-local-llm.py`: three existing checks pass.
- `python3 scripts/memory-product-smoke.py --binary target/debug/instantkv`: passed
  the actual CLI against an isolated real node. It covered create, exact replay,
  saved-preview replay without a model, read-only credentials, conflict exclusion,
  stale-revision rejection, correction, profile/context, restart, forgetting,
  replay rejection and raw tombstone erasure. Temporary state was removed.
- `./scripts/check.sh --repo`, `python3 scripts/check-repo.py`, `bash -n scripts/check.sh`
  and `git diff --check`: repository checks, links, script syntax and patch hygiene pass.
- Site `npm run check`, `npm test`, `npm run build`, `npm run verify`: pass.
  The build produced 39 pages; verification covered HTML links/assets, Markdown
  exports, search and machine-readable documentation, including the new guide.

## Product review changes

Repeated identical values no longer fill history. Last-confirmed time prevents an
older contradictory observation from becoming a current conflict. Conflicted
slots reserve capacity for resolution to existing evidence. Tombstones erase raw
identity labels as well as values, quotes, history, conflicts and source IDs.
Saved previews provide an exact retry path without another model call.

## Limits and next gate

No Ollama executable/model was installed for these checks. Extraction checks use
fake output; a quote's presence does not establish correct interpretation.
The subsequent [OpenCode trial](2026-10-09-opencode-live.md) exercised a connected
model through six fresh sessions. It does not validate Ollama extraction quality.

History and receipts are finite. The controller has no archival, compaction or
explicit restoration command. It does not provide multi-fact transactions or
consistent read snapshots. The chat harness retains no conversation history.
These limits need sustained-use feedback before broader product claims.

Managed records require a durable namespace without native TTL. The existing API
cannot preflight retention settings on an empty namespace. A create inheriting
native TTL is detected after commit; the error reports that the write committed.
Semantic expiry preserves tombstones. Native raw/API writes and existing backups
remain separate operator responsibilities.

The [roadmap](../roadmap.md#memory-product-tasks) tracks the installed-model trial,
long-term use, normal agent integration and later retrieval quality work.
