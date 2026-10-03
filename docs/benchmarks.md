# Benchmark reproduction

Use full pinned datasets. Keep raw outputs, configuration and the exact engine
commit. Separate retrieval, answer quality, structured operations and device tests.

## Full memory evidence

The frozen engine is `fafa202e165f9c467e8de344403437e704f9a24a`.
Full LongMemEval-S uses 500 questions with session-level source labels.
LoCoMo queries all ten histories and all 1,986 questions; positive recall scores
1,533 questions with source-turn labels. No new engine tuning occurred on these tests.

[Full results and limits](benchmarks/2026-10-04-full-retrieval/README.md) ·
[Campaign configuration](../eval/campaign.json) · [Runner guide](../eval/README.md).

Follow the runner guide to fetch pinned data, build the frozen engine, start a
fresh provider and run `eval/run.py --retrieval-only`. It records rankings,
returned contexts, latency and process measurements. Use the independent
verification script to check scores against official labels. Use
`eval/score_saved.py` for model QA from a completed saved-context pass.
Do not interpret failed API calls as valid answer-quality scores.

## Secondary BEIR tests

[Current BEIR reports](benchmarks/2026-10-04-search/README.md) retain dataset hashes,
rankings and verification receipts. SciFact, ArguAna and NFCorpus use full query
sets. Supermemory controls were recorded on 3 October. Earlier 12-question
LongMemEval samples are historical and superseded by the full run.

## Structured memory

```sh
cargo build --release --locked -p instantkv
python3 scripts/memory-bench.py --records 10000 --runs 3 --queries 300 \
  --output /tmp/instantkv-memory-benchmark.json
```

Three fresh databases, 10,000 records each. Each record has 512-byte content,
metadata, a topic, a tag and event time. Warm authenticated loopback HTTP,
keep-alive, concurrency one. Writes commit immediately. Results include p50,
p95, p99 and sampled native RSS. Recovery verifies each field after abrupt
process exits, then deletion and cursor continuation.

[Raw structured runs](benchmarks/2026-10-04-search/mac-arm64.json) ·
[Workloads and device targets](performance.md).

## Comparison rules

Use identical source documents and query budgets. Disclose transports and process
boundaries. SQLite includes its Python runner in RSS; local Supermemory retains
corpus scopes in one suite server. Parallel load affects latency. Do not derive
isolated speed or RAM ratios from these results.

Local Supermemory v0.0.8 uses direct embedding retrieval, with model extraction,
rewriting and reranking disabled. It does not represent the hosted product.
Measured Mac results do not establish phone performance, battery use or 10M-record
capacity. LongMemEval-V2, AMA-Bench, BEAM and larger record-scale tests remain incomplete.

[Evaluation policy](evaluation-policy.md) · [Roadmap](roadmap.md).
