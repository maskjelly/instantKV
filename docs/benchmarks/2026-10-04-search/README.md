# Bounded search update

Recorded: 4 October 2026. Runtime: `fafa202e165f9c467e8de344403437e704f9a24a`.
Fresh instantKV runs; historical Supermemory local controls from 3 October.
[Engineering notes](../../memory-benchmark-notes.md) · [Fixed design](../../history/search-design-2026-10-04.md).

| Workload | Queries | instantKV Recall@10 | Recorded Supermemory local |
| --- | ---: | ---: | ---: |
| BEIR SciFact | 300 | 81.43% | 74.80% |
| BEIR nfcorpus | 323 | 15.31% | 17.08% |
| BEIR arguana | 1,406 | 76.96% | 56.40% |
| LoCoMo evidence retrieval | 1,533 | 57.65% | 58.28% |
| LongMemEval-S session retrieval sample | 12 | 91.67% | 65.28% |

## Default search and optional expansion

ArguAna: 1,406 questions. Default Recall@10 76.96%;
expansion 77.03%. Rejections: 0 / 0.
Truncated queries: 688 / 701.
Reduced queries: 1149 / 1149.
Default and expanded p95: 46.826 / 49.535 ms.
Expansion is off by default. No qrels selected related words or parameters.

## Scope and inputs

Full BEIR ArguAna, NFCorpus and SciFact test splits; all ten LoCoMo histories;
fixed twelve-question LongMemEval-S pilot. Original text and qrels are unchanged.
Dataset hashes match the frozen [earlier input audit](../2026-10-03-suite/inputs.json).
The [earlier method](../2026-10-03-suite/README.md) records sources, exclusions and chunk limits.
Five ArguAna qrels point to absent corpus IDs; they remain misses for both systems.
The query's own document is excluded. Chunks are deduplicated before scoring.
No answer labels enter stored content. No extraction, answer generation or judging.

## Work and metrics

Local profile: 8 MiB cache; 20,000 index reads, 1,000 record candidates,
4 MiB record scan and 64 KiB maximum response per page. Input up to 16 KiB;
up to 64 original indexed terms selected by IDF times square-root query frequency.
WAND uses conservative per-term BM25 score bounds. Short searches score all postings.
Both preserve BM25 k1=1.2, b=0.75 and English stemming.
Expansion adds at most eight indexed terms at quarter weight, off by default.
Cursors bind normalized query, expansion settings and index generation.

`query_reduced` differs from `truncated`. Selected-query results can differ from
full-question scores. Truncated searches have no complete top-k guarantee.
Reports retain original questions, rankings, Recall/nDCG/MRR at 5, 10 and 20,
work counters, flags, latency samples and source hashes. Rejections count as misses.
Unexpected API errors stop a run.

Suite timings include pagination to twenty unique sources. SciFact uses the
existing top-ten harness; these timing paths measure different work.
RSS is sampled server memory, not peak or a phone result. Each binary runs alone.
Supermemory rankings and resource samples are historical controls, not fresh measurements.
These tests do not evaluate its hosted or full extraction/answer pipeline.

## Reports

- Default: [ArguAna](default/arguana.json), [NFCorpus](default/nfcorpus.json),
  [LoCoMo](default/locomo.json), [LongMemEval pilot](default/longmemeval.json).
- [Optional expansion ArguAna](expansion/arguana.json).
- [SciFact](scifact.json) and [independent verification](scifact-verification.json), [recovery](mac-arm64.json), [summary](summary.json).
- Independent per-query receipts: [default](default/verification.json), [expansion](expansion/verification.json).

## Reproduce

Build the runtime commit above. Prepare inputs with the pinned sources and
commands in the earlier method. Check input SHA-256 against each report. Then:

```sh
cargo build --release --locked
python3 scripts/retrieval-suite.py --dataset /tmp/arguana.json --baseline docs/benchmarks/2026-10-03-suite/arguana.json --output /tmp/default/arguana.json
python3 scripts/retrieval-suite.py --dataset /tmp/arguana.json --baseline docs/benchmarks/2026-10-03-suite/arguana.json --expand --output /tmp/expansion/arguana.json
python3 scripts/ranked-bench.py --dataset /tmp/scifact --baseline docs/benchmarks/2026-10-03-ranked/fresh-baseline.json --output /tmp/scifact.json
python3 scripts/memory-bench.py --records 10000 --runs 3 --output /tmp/mac-arm64.json
python3 scripts/verify-retrieval-suite.py --datasets /tmp --output /tmp/default/verification.json /tmp/default/arguana.json
```

Repeat the default command for nfcorpus, locomo and longmemeval.
The scorer needs `pytrec-eval-terrier==0.5.10`; runtime harnesses use the standard library.
A fresh comparison can supply `--supermemory-binary` instead of `--baseline`.
