# Small memory. Measured tradeoffs.

Published: 4 October 2026. Source MVP; unreleased.

instantKV stores facts, sources and task state for local agents.
The memory service needs no cloud API or embedding model.
Our aim is useful recall with little extra load beside a local LLM.

## How we improved recall

Our first keyword path required every query word to match.
It reached only 3.75% Recall@10 on BEIR SciFact.

We added BM25 search with English stemming.
It ranks shared words by frequency and document length.
Rare words get more weight. Stemming joins forms such as “running” and “run”.
A query can match some words instead of requiring all words.

Records and search indexes share one redb database.
Writes, deletes and expiry cleanup update both in one transaction.
The Rust binary grew from 7.99 to **8.28 MiB**.

## The measured results

| Workload | Evidence | Queries | instantKV Recall@10 | Supermemory local Recall@10 |
| --- | --- | ---: | ---: | ---: |
| BEIR SciFact | Documents | 300 | 81.43% | 74.80% |
| BEIR NFCorpus | Documents | 323 | 15.31% | 17.08% |
| BEIR ArguAna | Documents | 1,406 | 12.73% | 56.40% |
| LoCoMo | Turns | 1,533 | 57.65% | 58.28% |
| LongMemEval-S pilot | Sessions | 12 | 91.67% | 65.28% |

Recall@10 is the share of labelled evidence found in the first ten results.
Different datasets have different evidence units and relevant-document counts.
Compare the two systems within each row, not scores across rows.

Both systems used the same text on one Apple M4 Pro.
Each provider ran alone with fresh state.
Supermemory used its official local v0.0.8 binary and bge-base embeddings.
We saved source text directly, without extraction, reranking or query rewriting.
There was no answer model or judge.

LoCoMo uses ten full histories and 1,533 questions with complete evidence.
The LongMemEval-S pilot uses twelve fixed questions with full histories.
These are evidence retrieval tests, not official answer-quality scores.

## What the small footprint costs

SciFact top-ten query p95 was **1.31 ms** for instantKV and **53.82 ms** for Supermemory local.
Sampled process-tree RSS was **22.72 MiB** and **2,606.55 MiB** respectively.
These are warm local HTTP measurements from one run; samples do not measure peak RSS.

Indexing adds disk space and write work.
Our SciFact database used **81.00 MiB**.
Save p95 rose from **6.76 ms** in the old path to **11.81 ms** with BM25.
The new suite uses different ingestion batches, so it makes no per-record save comparison.

LoCoMo query p95 was **0.44 ms vs 23.37 ms**.
Sampled RSS was **21.30 MiB vs 2,447.28 MiB**, with near-parity overall Recall@10.

The largest instantKV RSS sample across the four new workloads was **23.75 MiB**.

Known topics and time ranges can use ordered filters instead of ranking.
Three 10,000-memory runs measured topic-query p95 at **0.130–0.137 ms**.
They verified all **30,000** records after abrupt process restarts.
[Raw structured-memory samples](benchmarks/2026-10-03-ranked/mac-arm64.json).

## Where we need to improve

NFCorpus favors Supermemory: **17.08% vs 15.31% Recall@10**.
It had no rejected or truncated instantKV queries.

ArguAna rejected **1,149 of 1,406** instantKV questions under the default query contract.
All **257** accepted searches were truncated.
Those failures count in our **12.73% Recall@10** score.
We need better long-query handling before claiming good counterargument recall.

LoCoMo is close overall. We lead on single-hop recall: **66.61% vs 61.85%**.
Supermemory leads on multi-hop recall: **42.34% vs 29.34%**.
It also leads on temporal recall: **70.26% vs 67.06%**.
Connections across turns need work.

The LongMemEval-S pilot favors instantKV overall, but it misses one of two preference questions.
Twelve questions cannot establish a full-benchmark ranking.

Each default search page limits postings, candidate records and scanned bytes.
Queries allow at most 1,024 bytes and 64 indexed terms.
Check `truncated`: a bounded result may not be the complete top-k.

## What Supermemory does well

Its published architecture extracts contextual facts, links corrections and keeps source context.
It also records source dates and event dates.
These features target preferences, changed facts, time questions and multi-session reasoning.
[Supermemory's LongMemEval report](https://supermemory.ai/research/longmembench/) describes that pipeline.

Our direct-memory test does not run this full pipeline.
Its published 97% result includes aggregation and answer judging.
That result is not directly comparable with our evidence-session recall.

## The next steps

1. Split long questions into bounded queries. Combine ranks under a total work limit.
2. Improve bounded BM25 scoring. Check it against exhaustive rankings on held-out queries.
3. Add optional nearby turns, session links and app-defined correction links.
4. Test an optional local semantic adapter. Report its recall, RAM, disk, latency and energy costs.

These changes are planned. They have not produced new gains yet.
The default service will stay model-free.
Full LongMemEval runs, real-agent answer tests and phone measurements remain planned.

Read the [suite method and raw rankings](benchmarks/2026-10-03-suite/README.md)
and the [SciFact report](benchmarks/2026-10-03-ranked/README.md).
An independent trec_eval check verifies Recall, nDCG and MRR.

Dataset sources: [BEIR](https://github.com/beir-cellar/beir/wiki/Datasets-available),
[LoCoMo](https://github.com/snap-research/locomo),
and [LongMemEval](https://github.com/xiaowu0162/longmemeval).
