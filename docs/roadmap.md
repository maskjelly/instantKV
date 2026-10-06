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
| 1 | Clear onboarding and documentation | One working source path; generated site and links pass |
| 2 | Real local-agent continuation | Actual model saves, resets, restores and continues; complete traces and failure cases |
| 3 | Storage and upgrade hardening | Disk-full/commit faults, writer compatibility and restore drills |
| 4 | Memory MVP release | Matching tested binaries, checksums and fresh-install tests |
| 5 | Retrieval improvements | Held-out task gains after the frozen campaign, with measured resource costs |

Retired-session cleanup, migration tools and observability need separate implementation work.
Native phone support and physical ARM-board measurements remain pending.
[Performance and device targets](performance.md).

## Evaluation status

The committed 4 October reports contain full LongMemEval-S and LoCoMo retrieval.
Full native LongMemEval-S QA scored 85.20% (426/500) using GPT-6 Luna as reader and judge.
This is a model variant, not official leaderboard parity. Competitor QA remains incomplete.
LongMemEval-V2, AMA-Bench, BEAM and 100K–10M+ record tests remain incomplete in the published evidence.

Keep the engine frozen during the finite campaign. Preserve failed and interrupted runs.
Real local-agent tests and storage smoke experiments do not substitute for full suites.
[Full results](benchmarks/2026-10-04-full-retrieval/README.md) · [Evaluation policy](evaluation-policy.md).

## Later proposals

Portable export/import comes before multi-device synchronization.
Phone bindings need lifecycle, sandbox, backup and energy tests on named devices.
Optional embeddings must earn their model, index and runtime costs.
[Distributed consolidation](proposals/distributed-memory.md) and managed hosting remain proposals without a delivery date.
