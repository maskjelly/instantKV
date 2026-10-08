# Use the memory controller

This optional, source-only Python adapter adds corrections, provenance and
forgetting beside the existing instantKV node. It is unreleased. It does not
change the native Rust API or automatically capture conversations.

Python 3 and a current source build are enough for the deterministic commands.
Among these CLI commands, only `capture` calls a model, after you explicitly
select an already installed local Ollama model. The adapter uses the Python
standard library. It retains structured facts and bounded history, not transcripts.

For normal coding-agent use, [connect OpenCode](opencode-controller.md). It uses
OpenCode's existing provider and the same deterministic lifecycle. It needs no
Ollama installation. Provider inference and memory storage are separate choices.

## Start from source

From this repository, build and start a separate local node:

```sh
cargo build --release --locked -p instantkv
./target/release/instantkv start --dir "$HOME/.local/share/instantkv-controller"
```

Leave it running. It creates private credentials and reuses the same database
on restart. Use one node per data directory. The default URL is
`http://127.0.0.1:8080`; use `start --bind 127.0.0.1:8081` and the matching
controller `--url` if that port is occupied.

**Use a durable namespace with no default or required native TTL.** The default
`knowledge` namespace in [the local profile](../config/local.toml) meets this
requirement. Keep that condition in custom configurations. Tombstones must not
expire, because their removal would let forgotten facts return. Use proposal
`valid_until_ms` for semantic expiry instead.

The API cannot inspect namespace configuration or disable inherited TTL. The
controller rejects managed records with `expires_at_ms` set, including in a
write response. Such a write is already committed. Fix the namespace TTL
configuration before further use; an error does not always mean nothing saved.

In another terminal, start at the repository root:

```sh
cd examples
controller_secrets="$HOME/.local/share/instantkv-controller/.instantkv/credentials.env"
memory() {
  python3 -m memory_controller \
    --url http://127.0.0.1:8080 \
    --secrets-file "$controller_secrets" \
    --namespace knowledge --scope personal "$@"
}
umask 077
controller_work=$(mktemp -d)
```

Keep global options **before** the subcommand. Run from `examples/`, or set
`PYTHONPATH` to that directory. Credentials come from `INSTANTKV_APP_TOKEN`
inside the private file. The adapter reads the file; it never sources it.
There is no token argument or environment override. Keep tokens out of shell
history and committed files.

## Create, read, correct and forget

Create one reviewed proposal as a file. `source.text` is a grounded quote from
the user turn, not a saved transcript. Use stable source IDs from your runtime.
The example event times are fixed for reproducibility.

```sh
cat > "$controller_work/create.json" <<'JSON'
{
  "entity": "user",
  "attribute": "response_style",
  "value": "short bullets",
  "kind": "preference",
  "operation": "assert",
  "source": {
    "id": "guide/turn-1",
    "text": "Please use short bullets.",
    "role": "user",
    "occurred_at_ms": 1791504000000
  },
  "valid_until_ms": null
}
JSON
memory apply --file "$controller_work/create.json"
memory apply < "$controller_work/create.json"
memory profile --max-bytes 8192
memory context "bullets" --max-bytes 8192
memory inspect user response_style > "$controller_work/inspection.json"
```

Apply returns `key`, `revision`, `status` and `replayed`. The first application
has status `created`; identical retry sets `replayed` and does not write again.
Reuse the exact JSON on retry. Reusing a source ID with another payload in the
same slot fails. One source ID may supply facts to different slots.

Inspection returns `key`, `revision`, `scope`, `entity`, `attribute`, `state`,
`value`, `kind`, `source`, `valid_until_ms`, `history`, `conflicts` and `expired`.
Profile and context return `items` and `truncated`. Each item includes `key`,
`revision`, `entity`, `attribute`, `value`, `kind`, `source` and `valid_until_ms`.
They exclude forgotten, expired and unresolved conflicted slots. Check
`truncated`; an incomplete result is not proof that a fact is absent.

A different `assert` records a conflict instead of silently replacing the fact.
It prints a `conflict` receipt and exits nonzero so a caller must review it.
An older observation can return `stale`; this does not make it current truth.
`duplicate` recognizes the same value. An explicit `correct` returns `corrected`.

Review `inspection.json`. Build a correction using its observed revision:

```sh
python3 - "$controller_work" <<'PY'
import json
from pathlib import Path
import sys

folder = Path(sys.argv[1])
detail = json.loads((folder / "inspection.json").read_text())
proposal = json.loads((folder / "create.json").read_text())
proposal.update(operation="correct", value="brief numbered points",
                expected_revision=detail["revision"])
proposal["source"] = {
    "id": "guide/turn-2", "text": "Correction: use brief numbered points.",
    "role": "user", "occurred_at_ms": 1791504001000
}
(folder / "correct.json").write_text(json.dumps(proposal))
PY
memory apply --file "$controller_work/correct.json"
memory profile
memory inspect user response_style > "$controller_work/inspection.json"
```

If the revision changed, inspect again and review the new state before rebuilding
the correction. Never retry by removing `expected_revision`.

Stop the node with Ctrl-C and repeat the same `start --dir` command. In the other
terminal, `memory inspect user response_style` should still show the correction.

Review the current inspection before forgetting, then supply that revision:

```sh
controller_revision=$(python3 - "$controller_work/inspection.json" <<'PY'
import json
import sys
with open(sys.argv[1]) as stream:
    print(json.load(stream)["revision"])
PY
)
memory forget user response_style --expected-revision "$controller_revision"
memory profile
memory inspect user response_style
memory apply --file "$controller_work/create.json"
```

Forget returns status `forgotten`. Inspection shows state `forgotten`, null
`value`, `kind`, `source`, `valid_until_ms`, and empty `history` and `conflicts`.
Replay fails; default ingestion cannot restore the slot. A content-free
tombstone remains to enforce that rule. Explicit restoration is not supported.
Forget does not erase existing backups or unrelated raw writes. Keep the private
example files only as long as needed; remove them with `rm -r "$controller_work"`.

## Optional capture

Start Ollama with cloud features disabled and select an already installed local
model. Loopback alone does not prove that inference stays offline. Capture also
rejects known cloud-backed model metadata or cloud tags. These commands do not
download a model. The input is one user turn; assistant answers are not facts
to capture.

```sh
OLLAMA_NO_CLOUD=1 ollama serve
```

See [Ollama's cloud-disable instructions](https://docs.ollama.com/faq#how-do-i-disable-ollama-cloud-features).
Run the remaining commands in the controller terminal:

```sh
cat > "$controller_work/turn.txt" <<'TEXT'
I prefer tea without sugar.
TEXT
memory capture --file "$controller_work/turn.txt" \
  --source-id guide/turn-3 \
  --model YOUR_INSTALLED_MODEL > "$controller_work/preview.json"
```

Preview returns `{"proposals": [...], "applied": false}` and does not contact
the memory node. Each proposal shows its final source ID, quote and timestamp.
The CLI sets the current Unix milliseconds once per invocation; the model cannot
invent that timestamp. Use `--occurred-at-ms 1791504002000` for a historical event.
Read the proposals, then apply the exact saved preview:

```sh
memory apply --file "$controller_work/preview.json"
```

No model call is needed for this step or an identical file retry. Apply accepts
either a single proposal object or exactly `proposals` and `applied: false`.
The list holds at most eight proposals. All proposals are validated before any
write; an invalid wrapper or proposal leaves memory unchanged. Once writes start,
each fact commits independently. An outcomes payload with `applied: true` is not
accepted as input.

To explicitly request extraction and application in one invocation:

```sh
memory capture --file "$controller_work/turn.txt" \
  --source-id guide/turn-4 \
  --model YOUR_INSTALLED_MODEL --apply
```

This runs extraction again; it does not apply a previous preview. Output has
`applied: true` and `results`, each with `index` and either `receipt` or `error`
plus a fixed `next_action`. Applying a saved preview uses this same result shape.
That flag means application was requested, not that every proposal committed.
Any failure or conflict gives a nonzero exit. Facts commit independently; inspect
partial results. Use the saved preview path when you need exact retries;
fresh capture can vary the timestamp and model output. Extraction
failure happens before any memory writes. Model-down errors suggest deterministic
`apply`; no model is needed for reads, corrections or forgetting.

The optional `local-memory-chat.py` harness answers from the current user turn
plus freshly read profile/context. It does not retain or replay a conversation
transcript. Capture is opt-in and requires review; limited memory history is not
a replacement for chat history.

From `examples/`, connect the harness to the same node:

```sh
python3 local-memory-chat.py --model YOUR_INSTALLED_MODEL \
  --secrets-file "$controller_secrets" --scope personal --capture
```

Use `/profile`, `/inspect user response_style` and `/forget user response_style`
for management. Forget shows the current record and requires a typed confirmation.
Use the deterministic CLI for corrections and exact saved-proposal retries.

## Limits and recovery

Input files and stdin accept at most 65,536 bytes for `apply`, and 16,384 UTF-8
bytes for `capture`. Apply takes one proposal or the strict preview envelope;
bare arrays, duplicate fields and
non-finite numbers are rejected. `--file -` also reads stdin.

| Limit | Bound |
| --- | --- |
| Scope, entity, attribute | 128 UTF-8 bytes each |
| Value / source quote / source ID | 1,024 / 512 / 256 UTF-8 bytes |
| Managed metadata / content | 8,192 / 16,384 bytes |
| Context query / maximum output budget | 16,384 / 65,536 UTF-8 bytes |
| History / conflicts / replay receipts per slot | 8 / 8 / 24 |

Aggregate metadata can fill before the item counts. Full history, conflicts or
receipts fail instead of dropping provenance or retry protection. Inspect the
slot; there is no automatic compaction or supported limit-reset operation.
Repeated identical values add a receipt, without filling history. They advance
the last-confirmed time while retaining the original source quote. Conflicted
slots reserve room for correction to existing evidence; a larger new correction
can still exceed the metadata limit. Forgotten records retain identity hashes,
revision data and generic native metadata, without raw identity labels or facts.
Profile/context work and output are bounded; they can return `truncated: true`.
Context uses the node's BM25 search, not embeddings or semantic graph retrieval.
`--max-bytes` must be between 128 and 65,536 bytes.

| Failure | Next action |
| --- | --- |
| Node unavailable or write timed out | Start the node; inspect or retry identical JSON. A submitted write may have committed. |
| Permission denied | Check the credential file and namespace grants. Writes need `put`; reads need `get` and `list`. |
| Revision changed | Inspect, review and use the new revision for an intentional correction/forget. |
| Source ID reused with another payload | Retry original JSON; use a new ID only for a new observation. |
| Node quota full | Review namespace capacity and unused records. Forget keeps a tombstone and need not free a slot. |
| Slot limits full | Inspect provenance and bounds. Do not erase retry protection to force a write. |
| Record format or TTL rejected | Check namespace configuration; fix default/required TTL. A rejected write response may follow a committed write. |
| Model unavailable or output rejected | Start your installed local model, or use reviewed JSON with `apply`. |

All failures exit nonzero and omit credentials and input text from diagnostics.
Normal JSON output contains memory values; treat it as private data. Missing
inspection exits nonzero. Loopback HTTP origins only; redirects are rejected.

For read-only use, provision a private file whose `INSTANTKV_APP_TOKEN` value is
the node's reader credential. It can inspect, profile and context within its
grants; apply and forget are denied. There is no client-side permissions bypass.

## Verify and stop

From the repository root, after building the node:

```sh
python3 scripts/memory-product-smoke.py --binary target/release/instantkv
```

This single isolated scenario checks creation, retry, read-only grants, conflict,
correction, profile/context, restart, forgetting, replay rejection and raw
tombstone erasure. It calls no model and retains no private output. Passing it
does not verify extraction quality with a real installed model.

Stop the adapter to roll back. The native node and existing memories remain
usable. Managed records need explicit handling before a future controller-format
upgrade; do not silently reinterpret them. See the [native memory guide](memory-mvp.md)
for storage and transport limits.
