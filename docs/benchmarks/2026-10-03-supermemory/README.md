# Local retrieval comparison: instantKV and Supermemory

Historical literal baseline. Ranked search is now available; see the
[new comparison](../2026-10-03-ranked/README.md). This report is unchanged.

Status: complete. Measured on 2026-10-03. One full run per system.

| Measurement | instantKV | Supermemory local v0.0.8 |
| --- | ---: | ---: |
| SciFact Recall@10 | 3.75% | 74.80% |
| SciFact nDCG@10 | 0.0363 | 0.6324 |
| SciFact MRR@10 | 0.0367 | 0.5997 |
| SciFact query p95 | 15.646 ms | 58.177 ms |
| Title hit@10 | 84/100 | 75/100 |
| Title query p95 | 14.530 ms | 42.632 ms |
| Save completion p95 | 6.759 ms | 361.309 ms |
| Post-boot sampled RAM | 6.20 MiB | 1,882.11 MiB |
| Largest sampled RAM | 20.91 MiB | 2,523.75 MiB |
| Native binary | 7.99 MiB | 258.20 MiB |

All 5,185 saves returned successfully for each system. All 300 test queries and
100 title queries completed. Supermemory removed Unicode replacement characters
from six returned records; the report records each change. instantKV returned
each saved string exactly.

**Interpretation:** instantKV has a much smaller footprint in this workload.
Supermemory retrieves far more relevant documents from natural-language queries.
The faster literal scans do not establish better semantic retrieval. The title
test measures partial-title lookup and does not establish general exact-match
superiority. These results apply to the tested configurations on this Mac.

[Raw report and all samples](scifact.json). Every relevance metric and percentile
was independently recomputed from the report and the original relevance file.

Dataset: [BEIR SciFact](https://github.com/beir-cellar/beir/wiki/Datasets-available).
The test split has 300 judged queries over 5,183 scientific documents. This is a
document-retrieval test, not a test of an agent's reasoning or personal memory.

Both systems receive the same title and abstract text. Two long documents are
split at 9,500 characters. No text is discarded. The result has 5,185 stored
chunks. Rankings use source document IDs and remove duplicate chunk hits.

## Method

- Host: Apple M4 Pro, macOS ARM64. One client, sequential authenticated local HTTP.
- instantKV: current release-build binary from source, default local profile.
- Supermemory: official `server-v0.0.8` macOS ARM64 binary; release SHA-256 verified.
- Supermemory uses local `Xenova/bge-base-en-v1.5` embeddings, 768 dimensions.
- Direct `/v4/memories` writes bypass extraction. Query rewriting and reranking
  are disabled. No generation model or paid API is used.
- Supermemory requires a provider setting at boot. An unused placeholder points
  at local port 9; this run does not use the extraction provider.
- Both save calls return the saved content. instantKV's returned content is checked
  for exact equality. Supermemory's returned text changes are recorded separately;
  a diagnostic found that it removes a Unicode replacement character from one
  source title. Its direct-memory API computes embeddings before returning.
  These are not queued-ingestion timings.
- Each system runs alone. Five untimed test queries warm retrieval before timing.
- RAM is sampled for each server and all its descendant processes. It includes
  Supermemory's separate graph engine. It is not a peak-memory measurement.

## Query contract

Supermemory receives the original SciFact query. It returns ten embedding-ranked
hits with threshold zero and no reranker.

instantKV supports at most eight literal terms and 256 query bytes. Only 71 of
the 300 original queries fit that shape. Its fixed adapter removes a short
stopword list, takes the first eight alphanumeric terms, and caps the result at
256 bytes. The adapter uses no relevance labels, model or corpus statistics.
All terms must match. Results stay in newest-first order. The client follows
cursors until it has ten distinct document hits or exhausts the candidates.

The instantKV result is an **adapted literal-retrieval baseline**. It is not a
semantic-search score or an official BEIR leaderboard submission. Latency covers
all cursor requests needed for that result, including empty scans.

A second workload uses the first three words of 100 evenly spaced document
titles. Both systems receive the same literal query, without a document-ID or
topic filter that would reveal the expected answer. The SciFact topic filter
on instantKV only selects the whole benchmark corpus.

## Metrics

- Recall@10: fraction of judged relevant documents found in the first ten hits,
  averaged over 300 queries.
- nDCG@10: relevance with a penalty for placing useful hits lower in the ranking.
- MRR@10: reciprocal rank of the first relevant hit, averaged over queries.
- Title hit@10: fraction of the 100 title queries that return their source document.
- p95: time within which 95% of measured operations finish.

The JSON retains every query, effective query, returned document ID, metric,
latency sample, dataset hash and binary hash. A `complete: true` field is required
before treating the report as final.

## Reproduce

Download [the pinned Supermemory release](https://github.com/supermemoryai/supermemory/releases/tag/server-v0.0.8)
and verify its platform SHA-256 before execution. Download the
[SciFact archive](https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip)
and extract it. The official archive MD5 is `5f7d1de60b170fc8027bb7898e2efca1`.

```sh
cargo build --release --locked -p instantkv
python3 scripts/test-compare-supermemory.py
python3 scripts/compare-supermemory.py \
  --dataset /path/to/scifact \
  --supermemory-binary /path/to/supermemory-server \
  --output /tmp/scifact-comparison.json
```

The harness uses temporary databases and stops both servers. Supermemory may
download local embedding assets on first use. Model assets and binary setup time
are outside the timed queries. Startup readiness does not mean cold embedding
initialization is complete.

This run does not test extraction quality, conversation updates, forgetting,
agent task success, battery use, phones, power loss or production workloads.
