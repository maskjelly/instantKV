# Local memory roadmap

The source MVP is implemented and unreleased.
The next milestone is a usable release with proven local-agent task continuation.
The [cleanup and release plan](project-plan.md) defines the work order and acceptance gates.

## Current source

- Structured `remember`, `recall`, `search`, `browse` and `forget`.
- Topic/tag/time indexes and bounded BM25 search with English stemming.
- Atomic record/index changes, revision conditions, quotas and expiry.
- Atomic checkpoint/latest-pointer commits and bounded restore.
- Embedded Rust core, authenticated HTTP, CLI and scoped MCP tools.
- Local profile, shared/private namespace setup, backup and restart tests.

[Memory contract](memory-mvp.md) · [Checkpoint contract](agent-memory.md) ·
[Verification history](history/checkpoints.md)

## Next milestones

| Order | Work | Acceptance |
| --- | --- | --- |
| 1 | Clear onboarding and harness setup | One working source path; Codex, Claude Code and OpenCode setup examples; generated site and links pass |
| 2 | Real local-agent continuation | Actual model saves, resets, restores and continues; complete traces and failure cases |
| 3 | Storage and upgrade hardening | Disk-full/commit faults, single-writer diagnostics, binary compatibility and restore drills |
| 4 | Memory MVP release | Matching tested binaries, checksums, fresh-install and upgrade tests on named platforms |
| 5 | Retrieval improvements | Held-out task gains after the frozen campaign, with measured resource costs |

For each supported harness, the release check must start from a clean config,
connect MCP, save one fact, stop, restart and recall that fact. Run the shared
server case with two concurrent adapters. Keep commands and expected results
in [Connect an agent](agents.md) and failure steps in [Operating one node](operations.md).

Retired-session cleanup, migration tools and observability need separate implementation work.
Native phone support and physical ARM-board measurements remain pending.
[Performance and device targets](performance.md).
Use the [private measurement guide](install-metrics.md) to track release
downloads and recent GitHub traffic. Actual source installations and active
local users remain unknown without an explicit opt-in signal.

## Evaluation status

The committed 4 October reports contain full LongMemEval-S and LoCoMo retrieval.
Full native LongMemEval-S QA scored 85.20% (426/500) using GPT-6 Luna as reader and judge.
This is a model variant, not official leaderboard parity. Competitor QA remains incomplete.
LongMemEval-V2, AMA-Bench, BEAM and 100K–10M+ record tests remain incomplete in the published evidence.

Keep the engine frozen during the finite campaign. Preserve failed and interrupted runs.
Real local-agent tests and storage smoke experiments do not substitute for full suites.
[Full results](benchmarks/2026-10-04-full-retrieval/README.md) · [Evaluation policy](evaluation-policy.md).

## Memory product tasks

The next controller milestone follows [this implementation contract](proposals/memory-controller.md).
It adds an optional local integration while keeping the Rust engine frozen.
These tasks are pending until implementation and verification are committed.

| ID | Task | Completion check | Dependency |
| --- | --- | --- | --- |
| M1 | Deterministic lifecycle and HTTP adapter | Create, retry, conflict, correction, expiry and content-free forgetting survive restart; writes remain revision-protected | Current API |
| M2 | Optional local extraction and interactive agent | Bounded, grounded proposals; preview before writes; context before answering; clear model/memory failures | M1 interface |
| M3 | Usable CLI and operator guide | First-use path, inspect/profile/context/correction/forget commands and a real-server restart scenario | M1 interface, M2 extraction |
| M4 | Integration and product review | Combined scenario passes; permissions and budgets hold; each completed task has a commit and validation evidence | M1-M3 |
| M5 | Installed-model product trial | Real conversation retains a preference, corrects it and forgets it; record errors, friction and runtime cost | M4 and an installed model |
| M6 | Broader memory quality | Evaluate temporal facts, ambiguous entities and paraphrases on separate development cases before proposing semantic retrieval or graph reasoning | M5 |

M1-M4 are the current implementation batch. M5-M6 are subsequent gates, not
claims that fake-model tests establish agent quality. No automatic cloud calls.

## Later proposals

Portable export/import comes before multi-device synchronization.
Phone bindings need lifecycle, sandbox, backup and energy tests on named devices.
Optional embeddings must earn their model, index and runtime costs.
[Distributed consolidation](proposals/distributed-memory.md) and managed hosting remain proposals without a delivery date.
