# Ranked document recall: instantKV and Supermemory

Measured 2026-10-03 on an Apple M4 Pro, macOS ARM64. One ranked retrieval run.
Both systems were rerun after the change, sequentially on this Mac with fresh databases.
The [fresh Supermemory baseline](fresh-baseline.json) is linked by hash from the ranked
report. The [historical literal baseline](../2026-10-03-supermemory/README.md) remains available.

| Measurement | instantKV BM25 | Supermemory local v0.0.8 |
| --- | ---: | ---: |
| SciFact Recall@10 | **81.43%** | 74.80% |
| SciFact nDCG@10 | **0.6852** | 0.6324 |
| SciFact MRR@10 | **0.6512** | 0.5997 |
| Query p95 | 1.309 ms | 53.816 ms |
| Save completion p95 | 11.815 ms | 354.486 ms |
| Largest sampled server + descendant RSS | 22.72 MiB | 2,606.55 MiB |
| Native binary | 8.28 MiB | 258.20 MiB |
| Partial-title hit@10 | 90/100 | 75/100 |

The recall gain is **6.63 percentage points**, or 8.9% relative.
This is a result for this dataset and these configurations, not general superiority.
SciFact contains scientific claims, not personal-memory conversations.
Supermemory uses local bge-base-en-v1.5 embeddings without reranking or query rewriting.
Extraction is bypassed; no generation model is used by either system.

## Method

- Same 5,183 title-plus-abstract documents, 300 judged test queries and dataset hashes.
- Two long documents split at 9,500 characters: 5,185 stored chunks; no discarded text.
- Original queries passed unchanged. No first-eight-term adapter.
- Fixed BM25 defaults: k1=1.2, b=0.75, positive IDF, English Snowball stemming,
  a fixed common-word list, OR matching. No relevance-label tuning or model calls.
- Source document IDs deduplicate chunk results. Relevance metrics use the first ten.
- Five untimed queries warm retrieval. Sequential authenticated loopback HTTP.
- Default 20,000-posting budget. All evaluated queries completed without truncation.
- Every query, ranking, work counter, latency sample and hash is retained in the
  [raw report](scifact.json). Runtime source: `5c6baed`, with no runtime changes during the run. Docs and harness
  metadata were dirty; binary, harness and baseline hashes identify the run.
- RSS is sampled, not peak RAM. Results exclude phones, battery use, inference,
  agent task success, power-loss recovery and model download/storage costs.

## Cost of the improvement

The old literal engine measured 7.99 MiB binary, 20.91 MiB sampled RSS and
6.759 ms save p95 on the same corpus. Ranked indexing measured 8.28 MiB,
22.72 MiB and 11.815 ms. Writes now maintain sparse postings in the same
transaction as records. **Old write latency is not preserved.**

The ranked SciFact database occupied **81.00 MiB**. Logical quotas exclude index
overhead. No Supermemory physical-disk result was recorded, so no disk advantage
is claimed. Corpus size and vocabulary affect disk growth.

Existing topic/tag/time retrieval, raw KV and checkpoint contracts remain available.
The separate [structured-memory report](mac-arm64.json) reruns their latency and
exact recovery checks with ranked indexing enabled.

## Reproduce

Download and extract the official [SciFact archive](https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip).
MD5: `5f7d1de60b170fc8027bb7898e2efca1`.

```sh
cargo build --release --locked -p instantkv
python3 scripts/ranked-bench.py \
  --dataset /path/to/scifact \
  --baseline docs/benchmarks/2026-10-03-ranked/fresh-baseline.json \
  --output /tmp/instantkv-ranked-scifact.json
python3 scripts/memory-bench.py --records 10000 --runs 3 --queries 300 \
  --output /tmp/instantkv-ranked-memory.json
```

To independently verify all query metrics with the same trec_eval library used by
BEIR evaluation, install `pytrec-eval-terrier`, then run:

```sh
python3 scripts/verify-retrieval.py --dataset /path/to/scifact \
  --report docs/benchmarks/2026-10-03-ranked/scifact.json
```

The ranked harness uses a fresh temporary database and verifies baseline dataset
hashes before running. It does not execute or modify Supermemory. To repeat that
provider, use the [original comparison harness](../2026-10-03-supermemory/README.md#reproduce).

## Next quality gates

Repeat on independent corpora and real local-agent tasks. Add measured multilingual
tokenization before claiming broad language support. Consider optional local
embeddings only when they improve task recall enough to justify their resource cost.
