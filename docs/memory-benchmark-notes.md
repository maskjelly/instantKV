# Small memory. Measured tradeoffs.

Updated: 4 October 2026. Source MVP; unreleased.

instantKV keeps facts, sources and task state beside a local model.
The memory service needs no cloud API or embedding model.
Our aim is useful recall with little extra load.

## What we changed

Our first literal search required every query word to match.
It reached 3.75% Recall@10 on BEIR SciFact.
BM25 with English stemming raised that result to 81.43%.
But ArguAna exposed a contract problem: 1,149 of 1,406 questions were rejected.
All 257 accepted searches hit work limits. Full-set recall was 12.73%.

We made four changes:

1. Accept questions up to 16 KiB. Select up to 64 original indexed terms from the whole question by rarity and square-root query frequency. Report `query_reduced`.
2. Keep exhaustive sparse scoring for short searches. Use WAND score bounds for larger searches. Skip low-score postings within the 20,000 index-read budget.
3. Add optional related words at one-quarter weight. Use a small fixed English list or up to eight words from the app. Expansion stays off by default.
4. Rerun the fixed datasets. Include failed and truncated questions. Verify every query with an independent trec_eval implementation.

Records and indexes still change in one redb transaction.
The database format is unchanged. Old ranked cursors need a new search after upgrade.
The binary is **8.31 MiB**, compared with 8.28 MiB before this update.

## Current results

| Workload | Queries | instantKV Recall@10 | Recorded Supermemory local |
| --- | ---: | ---: | ---: |
| BEIR SciFact | 300 | 81.43% | 74.80% |
| BEIR nfcorpus | 323 | 15.31% | 17.08% |
| BEIR arguana | 1,406 | 76.96% | 56.40% |
| LoCoMo evidence retrieval | 1,533 | 57.65% | 58.28% |
| LongMemEval-S session retrieval sample | 12 | 91.67% | 65.28% |

These are fresh instantKV runs on one Apple M4 Pro with fresh databases.
The Supermemory column reuses recorded 3 October local v0.0.8 results.
It uses bge-base embeddings, direct source text, no extraction, reranker or query rewrite.
Supermemory was not rerun here. No answer model or judge runs here.

Recall@10 is the share of labelled evidence found in ten results.
Compare systems within a row. The evidence units differ across datasets.
LoCoMo measures labelled turns from ten full histories.
LongMemEval measures source sessions for twelve fixed questions. It is a pilot,
not the full benchmark or an official answer-quality score.

## ArguAna: the gain and the limit

Default recall rose from **12.73% to 76.96%**.
Recorded Supermemory recall was **56.40%**.
All 1,406 questions were accepted. **Zero were rejected.**

Work limits still stopped **688 searches**.
**1149 questions** used fewer original terms.
The score includes both groups. These searches do not guarantee the complete
ranking for every word in the original question. Search does not infer argument stance.

Query p95 was **46.83 ms**,
including pages needed for up to twenty unique sources.
The previous 7.11 ms covered only the 257 accepted short questions.
That subset is not a speed comparison with the new complete set.
Recorded Supermemory p95 was **332.66 ms**.
Sampled instantKV RSS was **24.78 MiB**.

Optional expansion reached **77.03%**, with
**701 truncated searches** and p95
**49.54 ms**.
The gain is one extra question at @10. nDCG and MRR fell slightly.
This test does not justify making expansion the default.
The fixed list was set before the run and was not tuned to relevance labels.

## Small memory still has costs

SciFact top-ten query p95 was **1.55 ms**.
Sampled RSS was **23.14 MiB**.
The database used **81.00 MiB** and durable save p95 was
**12.57 ms**. Search indexes add disk space and write work.
The largest instantKV RSS sample in the four-workload and expansion runs was
**25.00 MiB**. Samples do not measure peak RAM.

Three fresh 10,000-memory runs verified **30,000 of 30,000 records** after abrupt restarts.
Known topics, tags and times still use ordered filters.
[Current structured-memory samples](benchmarks/2026-10-04-search/mac-arm64.json).

## Where we still need work

NFCorpus remains at **15.31%**, below the recorded **17.08%**.
LoCoMo remains close overall: **57.65% vs 58.28%**.
The same multi-hop and temporal gaps remain. The LongMemEval preference miss remains.
Better argument matching must improve recall without hiding work or output limits.

Next: tighter posting score bounds, optional source links and correction history,
a local semantic adapter with measured costs, and full answer-quality evaluations.
These are planned. Native phone performance and battery use remain unverified.

[Supermemory's report](https://supermemory.ai/research/longmembench/) describes a larger
extraction, aggregation and answer-judging pipeline. Its published 97% is not
comparable with our direct evidence retrieval. We have not evaluated that pipeline.

Read the [current method and raw reports](benchmarks/2026-10-04-search/README.md),
the [fixed design](search-improvement-plan.md), and the
[earlier suite](benchmarks/2026-10-03-suite/README.md).
