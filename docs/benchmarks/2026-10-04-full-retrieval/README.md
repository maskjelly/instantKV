# Full memory retrieval evidence

instantKV retrieves labelled source evidence with a local Rust index.
No embedding model or cloud API is used for retrieval.
These are **retrieval scores**, not official end-to-end QA scores.

| Full dataset | Questions with positive source labels | instantKV Recall@10 | SQLite FTS5 | Local Supermemory |
| --- | ---: | ---: | ---: | ---: |
| LongMemEval-S | 500 | 95.13% | 95.43% | Not complete |
| LoCoMo | 1,533 | 57.66% | 57.19% | 57.97% |

LongMemEval-S uses session-level source labels. LoCoMo uses turn-level source
labels. All ten LoCoMo histories and all 1,986 questions were queried. Its 446
adversarial questions and seven unresolved evidence references have no scored
positive source labels. They are not silently included in the recall average.

instantKV had zero query failures and zero truncated queries in these runs.
Its maximum sampled server RSS was **14.34 MiB** on LongMemEval-S and **11.25
MiB** on LoCoMo. Measurements used an Apple M4 Pro Mac with 24 GiB RAM. These are
Mac measurements. Native phone tests remain planned.

The results show strong session retrieval with a small local service. They also
show a remaining gap: local Supermemory has slightly higher observed LoCoMo
Recall@10. SQLite is close on LongMemEval-S. We do not claim broad superiority.

## Comparison limits

Supermemory is the local v0.0.8 embedding path with query rewriting, reranking
and model extraction disabled. This does not represent its full hosted pipeline.
All providers use the same source documents, lossless chunks and questions.
SQLite was rerun with the same response pagination budget as instantKV.

Parallel execution affects latency and RSS. No isolated speed ratio is claimed.
SQLite RSS includes the Python process. Supermemory retains separate corpus
scopes in one fresh server per suite; its RSS and disk figures are cumulative.
Do not use these values to claim a matched per-corpus RAM ratio.

Initial GPT-6 Luna QA runs hit API rate limits. Their failures remain in the raw
reports. Those scores are not valid quality comparisons. Full instantKV QA was rescored from saved contexts with a shared request/token
limiter. It scored **85.20%** (426/500), with zero API failures and a 95%
source-history-cluster bootstrap interval of **82.0–88.2%**. The reader and judge
are GPT-6 Luna. This uses the official judge rubric with a different model; it is
not official leaderboard parity. Competitor QA remains incomplete.

[QA summary](qa-summary.json) · [All answers and judgements](longmemeval-s--instantkv--qa.jsonl)
· [Model settings](longmemeval-s--instantkv--qa-report.json).

## Resource metrics

[Runtime metrics and samples](runtime-metrics.json) include query p50/p95/p99,
write request latency, startup, database size, sampled RSS and write throughput.
CPU utilization, CPU time, energy and separate index bytes were not recorded.
The resource process scopes and write guarantees differ between providers.
No isolated speed or RAM ratio is supported.

Recreate this export from the recorded result directory:

```sh
python3 scripts/export-eval-resources.py --results /path/to/results
```

The exporter checks complete question coverage and links runtime samples to the
published ranking hashes. It makes no model calls and estimates no missing metrics.

## Check the evidence

[Summary and settings](summary.json) and per-question ranking files are in this
folder. Dataset and runtime versions are pinned in
[the campaign configuration](../../../eval/campaign.json).
All five published ranking files were independently checked with `pytrec_eval`
against the official source labels. See [the verification receipts](verification.json). The complete raw histories, returned
records and run logs remain in the local campaign results folder.

Run `eval/run.py --retrieval-only` with the full pinned dataset and the provider
adapter to reproduce retrieval. Run `eval/score_saved.py` to score a complete
saved retrieval pass without repeating ingestion. See [the runner guide](../../../eval/README.md).

Recheck all QA answers, model identities, input coverage and the exact seeded
confidence interval from the recorded run:

```sh
python3 scripts/export-qa-evidence.py --run-directory /path/to/qa-run \
  --contexts /path/to/retrieval-run/contexts.jsonl
```
