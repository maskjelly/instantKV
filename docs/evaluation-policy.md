# Evaluation policy

**Optimize the architecture, not the benchmark. Any improvement must plausibly generalize to unseen memories and queries.**

## Current scope

Run a finite benchmark campaign on full official suite sizes. Quality comes first.
Keep storage local-first, lightweight, cheap to run and fast beside a local model.
API models may read retrieved context and judge benchmark answers. They are not
runtime dependencies of the memory service. Record their cost separately.
No autonomous recursive improvement goal is active. Freeze the engine during this
campaign. Do not tune against final questions or run automatic improvement loops.
State-of-the-art quality and efficiency remain targets, not current product claims.

## Required evaluation

Run full official LongMemEval-S, LongMemEval-V2 Small and Medium, LoCoMo,
AMA-Bench and BEAM suites at frozen milestones. Use BEIR as secondary IR evidence.
Test custom scalability at 10K, 100K, 1M and 10M+ memories. Record the actual
memory count; BEAM token counts are not record counts.

Measure Recall@1/5/10, nDCG@10, MRR, end-to-end QA accuracy, p50/p95/p99
query and write latency, throughput, RSS, disk/index size, startup time and
failure/truncation rate. Use null with a reason when a metric is unavailable.
Never fill an unmeasured metric with zero.

Break results down by single-hop, multi-hop, temporal, knowledge-update,
contradiction, semantic/paraphrase, open-domain, abstention and long-context tasks.
Keep official categories intact. Do not invent evidence labels for QA-only suites.

Compare relevant baselines: Supermemory, Mem0, Zep, SQLite FTS5/Tantivy,
BM25 and dense-vector retrieval. Use identical hardware, reader/judge models,
text, context budgets, durability and task policy where supported. Record every
unavoidable difference. Keep service-only and complete-system costs separate.
Do not call a hosted service a same-hardware baseline. Keep required models
optional and outside the memory service. Local evaluation should run offline
after declared setup downloads. Use the evaluation API credential only within the configured spending cap.

## Rules for a future authorized improvement loop

1. Benchmark current HEAD on development data.
2. Save every raw result and the exact configuration.
3. Find the largest meaningful weakness or regression.
4. Inspect representative development failures.
5. State a general architectural hypothesis.
6. Design one change that tests it.
7. Implement the smallest useful change.
8. Run correctness and regression tests.
9. Benchmark the change on development data.
10. Compare quality, latency, RAM, storage and failures with the previous best.
11. Keep a clearly better commit. Revert a worse or neutral candidate.
12. Add discovered failure modes to separate regression tests.
13. Repeat. If improvement is not statistically meaningful, choose the next weakness.

Use paired confidence intervals on matched questions for quality changes.
Use repeated fresh runs for resource and latency comparisons. Distinguish
variation across questions from variation across runs. Freeze seeds, budgets,
metrics and rejection gates before seeing candidate results.

## Initial development gates

These gates are fixed before the first new development run:

- Any correctness failure rejects the change.
- Any new failure or truncation increase rejects it unless documented as an intentional tradeoff.
- A quality-led change must have a positive paired 95% confidence interval and at least one percentage point absolute Recall@10 gain.
- A performance-led change must improve its preregistered cost metric by at least 10%, with no quality loss greater than one percentage point.
- Reject query p95/p99 or write p95 regressions above 10%.
- Reject sampled RSS regressions above 5%.
- Reject database/index size, binary size or startup regressions above 10%.
- Report all categories. Aggregate gains cannot hide a category regression above two percentage points.
- Missing required measurements or insufficient repetitions mean inconclusive, not accepted.

An explicit exception must state the cost, measured benefit and reason in the
ledger before promotion. Do not silently revise a gate after seeing a result.
An RSS sample is not a peak bound. Add peak instrumentation before claiming one.

## Major milestones

Freeze code and configuration. Run untouched official test sets with fresh
competitor databases. Run multiple repetitions. Calculate confidence intervals.
Publish raw outputs and tag the exact commit. Official reported QA scores need
the official reader/judge protocol; a local judge variant must have its own label.
No official final questions or answers may inform architectural tuning.

## Test exposure

The previously published BEIR and LoCoMo test sets and twelve LongMemEval-S
pilot questions have already been observed. Record this exposure permanently.
They can provide historical regression evidence but cannot become untouched
final holdouts again. Full official runs must disclose any prior overlap.
Do not carve a favorable new headline subset from those results.

When a dataset has only a test split, use separate synthetic/adversarial data
for development. Inspect official schemas and manifests without reading final
question/answer content before the frozen checkpoint.

## Ledger and previous best

Keep append-only result entries in `eval/ledger.jsonl`. Record commit SHA,
runtime SHA, binary and harness hashes, exact sanitized configuration, dataset
version/hash, hardware, raw paths/hashes, before/after metrics, hypothesis,
confidence intervals, gate decision and test exposure. Never store credentials.
Best configurations are immutable references. Candidate commits must be easy
to bisect or revert. Preserve historical reports and failed runs.

## Adversarial coverage

Add separate development cases for paraphrases, zero keyword overlap, stale
facts, updates, contradictions, duplicates, deletion, irrelevant noise, multi-hop
dependencies and temporal order. Retrieval success is not answer correctness.
Abstention needs a measured policy and QA evaluation, not fabricated positive qrels.

## Do not

- Tune against final test questions or inspect their errors for iteration.
- Hide failed queries, rejected writes, timeouts or incomplete suites.
- Change reader/judge models or settings between competitors.
- Cherry-pick subsets or optimize only Recall@10.
- Add benchmark-specific words, answer extraction rules or ID shortcuts.
- Weaken durability, delete protection, permissions or work budgets for a headline.
- Publish state-of-the-art, mobile, cost or speed claims without comparable evidence.
