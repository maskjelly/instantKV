# Small local memory: results and next steps

Updated: 2026-10-04. Engine: `fafa202`.

instantKV stores structured memory and ranks its content in one Rust process.
Retrieval needs no embedding model or cloud API. The model runtime decides what
to save and how to use returned facts.

## What we measured

| Full dataset | Scored questions | instantKV Recall@10 | SQLite FTS5 | Supermemory local |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval-S, source sessions | 500 | 95.13% | 95.43% | Incomplete |
| LoCoMo, source turns | 1,533 | 57.66% | 57.19% | 57.97% |
| BEIR SciFact, documents | 300 | 81.43% | Not run | 74.80% |
| BEIR ArguAna, documents | 1,406 | 76.96% | Not run | 56.40% |
| BEIR NFCorpus, documents | 323 | 15.31% | Not run | 17.08% |

All 500 LongMemEval-S questions and all ten LoCoMo histories were used.
LoCoMo queried 1,986 questions; 1,533 have scored positive source labels.
The 446 adversarial questions and seven unresolved references are excluded only
from positive-evidence recall. All five full memory retrieval files had zero
failures and zero truncations. Independent `pytrec_eval` checks used official source labels.

These are **retrieval scores, not end-to-end answer accuracy**. Full native LongMemEval-S QA scored **85.20%** (426/500) with zero
API failures and a 95% confidence interval of 82.0–88.2%. This uses the official
judge rubric with GPT-6 Luna as reader and judge, not official leaderboard model parity.
[QA settings and raw outputs](benchmarks/2026-10-04-full-retrieval/qa-summary.json). Competitor QA remains incomplete. The initial model runs hit API rate limits and are not valid QA comparisons.
SQLite has slightly higher observed LongMemEval-S recall. Local Supermemory has
slightly higher LoCoMo recall. No statistically significant win is established.

Supermemory local v0.0.8 uses direct embedding retrieval without model extraction,
query rewriting or reranking. It does not represent the hosted product.
BEIR controls are separate same-host runs recorded on 3 October. ArguAna has
688 truncated and 1,149 reduced queries; none were rejected. Expansion is off by default.

## How the engine stays small

Topic, tag and event-time indexes select records directly. BM25 ranks indexed
content. English stemming reduces word-form differences. WAND skips postings
that cannot improve the current top results. Fixed work and response budgets
bound each search. Writes keep records and indexes in one redb transaction.

Long questions select up to 64 indexed terms. The response reports `query_reduced`.
A separate `truncated` flag means a work limit stopped the search. Do not treat
that response as an exact top-k guarantee. Optional related-term expansion is off
by default: its small recall gain did not justify worse ranking metrics.

## The footprint

The measured Mac binary is **8.31 MiB**. Full LongMemEval-S retrieval reached
**14.34 MiB** largest sampled native RSS; LoCoMo reached **11.25 MiB**.
A separate three-run test stored 10,000 memories per database. Topic-query p95
was **0.152–0.173 ms**. Durable-save p95 was **6.665–6.923 ms**. All **30,000**
records were verified after abrupt process restarts. Samples do not measure true
peak memory, power-loss behavior, phone latency or battery use.

## What we improve next

1. Inspect missed evidence on separate development data. Improve paraphrases
   and zero-overlap queries without storing a large model in the core.
2. Preserve multi-hop links, event order and fact updates. Test contradictions,
   stale facts, deletion and abstention.
3. Reduce ArguAna work-limit hits with general index improvements. Keep budgets.
4. Finish full end-to-end QA and the remaining official suites. Publish failures,
   configuration, confidence intervals and raw results.
5. Measure 100K, 1M and 10M+ records, then real ARM boards and native phones.

Quality comes first. A change must justify its latency, RAM and storage cost.
Use development tests for iteration; reserve untouched tests for checkpoints.

[Full raw evidence](benchmarks/2026-10-04-full-retrieval/README.md) ·
[Secondary BEIR evidence](benchmarks/2026-10-04-search/README.md) ·
[Performance](performance.md) · [Evaluation policy](evaluation-policy.md).
