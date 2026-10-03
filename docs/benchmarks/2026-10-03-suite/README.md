# Local retrieval suite

Recorded: 3 October 2026. Same unchanged runtime as the ranked SciFact run.
This suite tests retrieval under default resource limits. It does not test answer generation.
Read the [short engineering article](../../memory-benchmark-notes.md).

## Results

| Workload | Evidence | Queries | instantKV Recall@10 | Supermemory local Recall@10 |
| --- | --- | ---: | ---: | ---: |
| BEIR SciFact | Documents | 300 | 81.43% | 74.80% |
| BEIR NFCorpus | Documents | 323 | 15.31% | 17.08% |
| BEIR ArguAna | Documents | 1,406 | 12.73% | 56.40% |
| LoCoMo | Turns | 1,533 | 57.65% | 58.28% |
| LongMemEval-S pilot | Sessions | 12 | 91.67% | 65.28% |

SciFact is the earlier frozen-runtime run. The other four workloads are new runs.
LoCoMo @20: 65.55% vs 65.24%; @10: 57.65% vs 58.28%. These differences are small.
LongMemEval-S uses twelve questions; do not present it as the full benchmark.

## Test sets

| Dataset | Source documents | Queries | Evidence unit |
| --- | ---: | ---: | --- |
| BEIR NFCorpus | 3,633 | 323; full test split | Documents; graded relevance |
| BEIR ArguAna | 8,674 | 1,406; full test split | Counterargument documents |
| LoCoMo | 5,882 turns; ten full conversations | 1,533 | Labelled source turns |
| LongMemEval-S | 574 source session IDs; twelve full histories | 12; fixed pilot | Labelled source sessions |

BEIR uses official test qrels. Five ArguAna qrels reference IDs absent from the official corpus.
They count as misses for both systems; [input audit](inputs.json) lists them. ArguAna excludes the query's own document before ranking.
LoCoMo excludes all 446 adversarial questions and seven questions with unresolved evidence.
Compound evidence references are preserved. The report lists every exclusion and reason.
LongMemEval selects the first two non-abstention IDs in lexical order for each of six question types.
Selection was fixed before retrieval. This is a pilot, not the full benchmark.
One repeated session ID is joined without discarding either source text.

No QA answers, generated observations, summaries or `has_answer` labels enter stored content.
Conversation speaker names, source dates and supplied image captions are included.
Images are not processed. Conversation namespaces keep corpus statistics isolated.
Dates in LoCoMo have no timezone; storage interprets them as UTC.
LongMemEval dates remain in source text; its storage event time is a fixed placeholder.
Neither path uses time filters in this test.

## Fixed providers and resource policies

- instantKV: original BM25 k1=1.2, b=0.75, English stemming and stopwords.
- instantKV: local profile, 8 MiB cache; default per-page query limits, no adapter.
- Supermemory: official local server v0.0.8, bge-base-en-v1.5, 768 dimensions.
- Supermemory: direct memories API, threshold zero, rerank false, rewriteQuery false.
- No answer model, judge, cloud API or automatic fact extraction.

Shared chunks contain at most 9,500 characters and 14,000 UTF-8 bytes.
The harness retains all text. Rankings deduplicate chunks to their source document or session.
instantKV follows bounded cursor pages until twenty unique sources or exhaustion.
Supermemory requests forty chunk candidates and keeps the first twenty unique sources.
A low number of unique sources after deduplication is retained, not filled with guessed matches.
This difference in result budgets is explicit; page counts are in each query row.

An instantKV HTTP 400 counts as zero evidence recall. Such questions are not removed.
A truncated search is included with its flag and work counters. It does not guarantee a complete top-k.
Unexpected API errors stop the run. `errors: 0` does not mean no query was rejected.

## Timing and resource measurements

Each provider runs alone, sequentially, on the same Apple M4 Pro.
Each run uses fresh state. Five untimed queries precede the measured queries.
Query latency covers local authenticated HTTP, decoding, deduplication and any cursor pages.
The report stores both all-query latency and accepted-query latency.
Use accepted-query latency when comparing systems; rejected requests can finish faster.

RSS samples cover the server and its descendants. They are not peak measurements.
Each report stores binary size/hash, sample values and instantKV physical database size.
instantKV ingests one record per request; Supermemory uses batches of sixteen.
Ingestion wall times are recorded. Do not compare them as per-record save p95.
Fresh Supermemory runs load/download their model before completing ingestion.
No mobile, energy or model-quality measurement is implied.

## Diagnostic findings

- ArguAna: 1,149 rejected questions; all 257 accepted searches truncated. Count every question in the published score.
- LoCoMo: instantKV leads single-hop Recall@10 (66.61% vs 61.85%); Supermemory leads multi-hop (42.34% vs 29.34%) and temporal (70.26% vs 67.06%).
- LongMemEval-S: both providers returned twenty unique sessions per query. instantKV recovered all labelled sessions at @20, but missed one of two preference questions at @10. This is a twelve-question pilot.
- NFCorpus query `PLAIN-133`: Supermemory found one labelled tumor-angiogenesis document in its first ten results; instantKV found none. The question used a blood-supply description. This is consistent with a wording gap, but does not prove the cause of the overall difference.

## Scores and audit trail

Every query row keeps its original text, ground truth, ranking, latency, HTTP status and limit counters.
Recall, nDCG and MRR are computed at 5, 10 and 20.
nDCG uses linear relevance gains, as trec_eval does for graded labels.
Any-evidence and all-evidence coverage are also reported.
Category scores are means over that category, not substitutes for the complete-set mean.
Different evidence units and relevant-document counts prevent cross-dataset score comparison.

The independent scorer verifies each query, not just the reported means.
Its receipt records report hashes and the installed scorer version.

## Reproduce

Use the binary SHA-256 values in the reports. Build instantKV at the recorded runtime commit.
Download the official Supermemory v0.0.8 macOS ARM64 binary and verify its release checksum.
Install Python 3 and use a separate environment for `pytrec-eval-terrier`.
The harness itself uses only the Python standard library.

Obtain inputs from the pinned URLs and revisions in each raw report:

- [BEIR dataset list](https://github.com/beir-cellar/beir/wiki/Datasets-available): NFCorpus and ArguAna archives.
- [LoCoMo](https://github.com/snap-research/locomo): commit `3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376`, `data/locomo10.json`.
- [LongMemEval cleaned data](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned): revision `98d7416c24c778c2fee6e6f3006e7a073259d48f`, `longmemeval_s_cleaned.json`.

```sh
python3 scripts/prepare-retrieval-suite.py --kind beir --input /tmp/nfcorpus --output /tmp/nfcorpus.json
python3 scripts/prepare-retrieval-suite.py --kind beir --input /tmp/arguana --output /tmp/arguana.json
python3 scripts/prepare-retrieval-suite.py --kind locomo --input /tmp/locomo10.json --output /tmp/locomo.json
```

For LongMemEval, put `longmemeval-source.json` beside the downloaded input:

```json
{"repository":"xiaowu0162/longmemeval-cleaned","revision":"98d7416c24c778c2fee6e6f3006e7a073259d48f"}
```

```sh
python3 scripts/prepare-retrieval-suite.py --kind longmemeval --input /tmp/longmemeval_s_cleaned.json --output /tmp/longmemeval.json
python3 scripts/test-retrieval-suite.py
python3 scripts/retrieval-suite.py --dataset /tmp/nfcorpus.json --supermemory-binary /tmp/supermemory-server-darwin-arm64 --output /tmp/nfcorpus-result.json
```

Repeat the last command sequentially for the other normalized inputs.
Do not run timed providers in parallel.

```sh
python3 scripts/verify-retrieval-suite.py docs/benchmarks/2026-10-03-suite/nfcorpus.json docs/benchmarks/2026-10-03-suite/arguana.json docs/benchmarks/2026-10-03-suite/locomo.json docs/benchmarks/2026-10-03-suite/longmemeval.json --datasets /tmp --output /tmp/verification.json
```
