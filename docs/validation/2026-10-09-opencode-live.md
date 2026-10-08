# OpenCode controller product trial

Date: 2026-10-09. Scope: optional controller MCP and actual OpenCode use.
This is a small development trial, not a benchmark or a release.
The Rust engine and frozen benchmark reports are unchanged.

## Implementation and installation

An independent implementation thread committed `4ef033b`, integrated as `492af30`.
It added the bounded Python stdio bridge, durable OpenCode V1 installer and five
focused grouped tests. Tools: `apply`, `inspect`, `profile`, `context`, `forget`.
Results include `{result, observed_at_ms}` in text and structured content. The
server clock grounds current observations without model-invented time.

The installer was checked in private isolated state before global installation.
Provider/model settings were preserved; the memory agent remains
`openai/gpt-6-luna`, limited to eight steps with shell and file reads denied.
Config and backups are mode 0600. Installed paths are independent of the checkout.
The old native adapter is disabled, with its state preserved. `opencode mcp list`
reported `instantKVMemory connected` for both installations.

The bridge exposes lifecycle tools only. Native KV/checkpoint tools remain on
the native interface. Existing native records are not automatically migrated.
Managed mode permits one owner per data directory; sharing requires external HTTP.

## Actual six-session result

OpenCode 1.18.35 used its existing connected `openai/gpt-6-luna` provider.
Every turn started a new `opencode run --pure --agent memory --format json` session.
The managed bridge restarted the local Rust node between sessions. State and
private events lived outside the checkout. The harness opened no provider credential.

| Session | Observed result |
| --- | --- |
| Save black tea without sugar | Empty profile; `apply` created `user / tea_preference`, revision 1 |
| Recall after restart | Profile returned the saved fact; answer said black tea without sugar |
| Change to green tea without sugar | Profile/inspect read revision 1; `apply` used `correct` and `expected_revision: 1`, returning `corrected`, revision 2 |
| Recall correction after restart | Profile returned the current green-tea value, revision 2; answer matched |
| Forget | Inspect supplied revision 2; forget returned `forgotten`, revision 3 |
| Recall after forgetting/restart | Empty, untruncated profile; answer said it did not know the preference |

A separate model-free read confirmed the retained tombstone: revision 3, state
`forgotten`, value/source null, history/conflicts empty. Creation and correction
quotes matched the synthetic user turns. Their observation times came from the
bridge's preceding profile clock.

All six processes succeeded: 17 model steps, 47.46 seconds of summed wall time.
OpenCode reported $0.00157503. A private ledger accounted $0.0016099125 conservatively
against a $25 product-trial cap. Neither figure is a verified provider invoice.
Maximum call costs were reserved before each session; unused reservations were
released after successful completion.

Reported token categories: 51 uncached input, 13,443 cache-read, 8,584 cache-write,
591 output and 134 reasoning. These are OpenCode categories, separate from the
memory service's resource cost. This is not a benchmark price claim.

## Checks and friction

- Five focused MCP/installer tests pass: protocol/schema bounds, lifecycle receipts,
  no mutation retry, EOF/SIGTERM cleanup, ownership and installer safety.
- The release binary passes the real-node CLI workflow: replay, permissions,
  conflict, correction, restart, forgetting and raw tombstone erasure.
- Repository checks pass. The global installed bridge connects without model calls.
- Site formatting, types, eight tests, static build and export/link checks pass.
- The collaborative browser confirmed new guides at desktop, tablet and 320-pixel
  widths without page overflow; wide tables scroll inside their bounds. Its host
  disconnected before a full visual/interaction pass. No completed screenshot,
  both-theme or keyboard/copy check is claimed for this publication.

Two recall answers called the readable `user/tea_preference` label a memory key
instead of copying the canonical `mc/...` key. Retrieved values and revisions were
correct. Agent presentation still needs review; this does not establish perfect
citations or capture quality.

CI passed both Linux runners but exposed a macOS fixture startup failure.
Python's default HTTPServer binding calls `socket.getfqdn`, which performs reverse
DNS. Fake model setup also took about 95 seconds on that runner, while the actual
model request checks passed. The fake native server wrote its PID before that
lookup and could not listen within the bridge's startup allowance. The fixtures
now bind literal loopback addresses through TCPServer and set their numeric
server identity without DNS. The Rust server and bridge allowance are unchanged.

The test also derives its wait from the eight-second bridge allowance plus a
bounded scheduling margin and cleans up subprocesses/pipes on failure. Existing
checks pass locally. Ad hoc checks delayed HTTP readiness by 5.5 seconds and
blocked reverse DNS while exercising the fixtures. The full local core verifier
passed, including schemas, offline evaluation, demos and restart.

The trial covers one synthetic preference and one cloud provider. It does not
establish offline inference, ambiguous-entity handling, paraphrase recall, sustained
use, large profiles or concurrent shared-server agent quality. Ollama extraction
still has only fake-model validation here. Evidence capacity is finite; safe
archival/compaction and explicit restoration remain open tasks.

[OpenCode setup](../opencode-controller.md) · [Lifecycle limits](../memory-controller.md)
· [Technology learning map](../technology.md)
