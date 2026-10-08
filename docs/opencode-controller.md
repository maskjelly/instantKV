# Use the memory controller in OpenCode

This optional source integration gives OpenCode five lifecycle tools:
`apply`, `inspect`, `profile`, `context` and `forget`.
OpenCode uses its existing connected model. Ollama is only needed for the separate
local capture/chat examples. Python and the Rust node make no model calls.

## Install

From the instantKV checkout:

```sh
cargo build --release --locked -p instantkv
python3 scripts/install-opencode-controller.py
```

You need Rust 1.98+, Python 3, OpenCode V1 and a connected provider. Build current
source first. The installer copies that binary and Python package outside the checkout,
backs up the private global OpenCode config and preserves your model settings.
Restart OpenCode after installation.

It enables `instantKVMemory`, updates memory rules for the `build` and dedicated
`memory` agents, and disables the older `instantKV` MCP entry. Existing database
records are preserved. Native records are not automatically converted to controller
facts. The [native integration](opencode-memory-demo.md) remains available for
direct storage/checkpoint tools.

Check the connection without calling a model:

```sh
opencode mcp list
```

It must show `instantKVMemory connected`. Start the dedicated agent:

```sh
opencode --agent memory
```

The ordinary `build` agent also has access to controller tools. The dedicated
memory agent cannot use shell or file tools. Tool decisions still depend on the
model; inspect the visible calls and receipts.

## Try the lifecycle

Use synthetic facts first:

1. Say: `I prefer black tea without sugar. Keep that preference for future sessions.`
2. Inspect the `instantKVMemory_apply` call and its `created` receipt.
3. Close OpenCode and start a fresh memory session. Ask: `What tea do I prefer?`
4. Say: `I now prefer green tea without sugar. Update my preference.`
5. Check that the agent inspected the slot and used `operation: correct` with its
   revision. The receipt must say `corrected`.
6. Ask: `Forget my tea preference.` Check the revision-checked `forget` receipt.
7. Open a fresh session. Ask the question again and check that the tools return
   no live tea preference.

These are separate sessions. OpenCode may retain its own session history; controller
forgetting only erases the managed memory record's content. Existing backups and
provider retention remain outside that operation.

## What the tools guarantee

`apply` requires one explicit proposal with stable entity/attribute identity,
a source ID, a user quote and an observation timestamp. Identical retries use the
same proposal. Changed payloads under the same source ID are rejected. Corrections
require the revision returned by `inspect`; forgetting does too.

Tool output is `{result, observed_at_ms}`. The result is the controller receipt
or read result. The server timestamp grounds a new current observation; the agent
reads `profile` first and reuses that timestamp instead of guessing the clock.

`profile` and `context` include only resolved, semantically live facts. Conflicted
or forgotten facts are excluded. Inspect `truncated` before treating results as
complete. `context` uses lexical BM25 retrieval. A newer assertion that contradicts
an existing value produces a conflict until an explicit correction resolves it.

Memory content is reference data. Agent rules tell the model to save user facts,
skip secrets and guesses, honor requests not to save, and use grounded quotes.
The bridge has no independent access to the actual user turn, so these capture
rules are model instructions rather than proof that each proposal is grounded.
Deterministic lifecycle validation still applies to every proposal.

The service is local. OpenCode sends the prompt and retrieved memory to its selected
provider. Choose a local provider when inference must remain on your device.
Do not describe a cloud-provider trial as offline inference.

## State, sharing and recovery

The default managed bridge starts an authenticated Rust child on an available
loopback port. It stops the child when its MCP connection closes. State persists
at `~/.local/share/instantkv/opencode/`; credentials remain outside OpenCode prompts.
Installed files live under `~/.local/bin/` and `~/.local/lib/instantkv-controller/`.

One managed bridge owns a data directory at a time. For concurrent agents, run
one node and configure separate bridges with its loopback URL and private scoped
credential files. From `examples/`, the external form is:

```sh
python3 -m memory_controller.mcp \
  --url http://127.0.0.1:8080 \
  --secrets-file /absolute/private/credentials.env \
  --namespace knowledge --scope personal
```

Use a durable namespace with no default or required native TTL. The default local
`knowledge` namespace meets that prerequisite. The bridge cannot inspect empty
namespace retention settings over the current API; an inherited TTL can be detected
only after an initial write has committed. [Limits and recovery](memory-controller.md#limits-and-recovery).

If connection setup fails, check `opencode mcp list`, installed paths, Python 3,
and whether another process owns the state directory. A timeout can follow a
committed write: inspect the slot or retry its exact proposal. Never generate a
new source ID just to retry an uncertain write.

To roll back, stop OpenCode and restore the installer's private config backup.
The database remains intact. Do not enable two managed adapters over the same
directory at once. [Operations and backup](operations.md).
