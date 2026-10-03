# Full official benchmark campaign

Scope: full dataset sizes, frozen instantKV runtime, GPT-6 Luna reader and judge.
API cap: $250 across every run. Storage remains local and model-free.
This is a finite evaluation task. No autonomous improvement goal is active.

Configuration: [campaign.json](campaign.json). Sources and versions are pinned.
Credentials belong in a private file outside this checkout, never a command argument
or committed configuration. The process-safe budget ledger reserves a conservative
maximum before each call. Failed or ambiguous requests retain their accounted cost.

Full suite QA with GPT-6 Luna is a model variant of the published protocols.
Do not label it official leaderboard model parity. Record reader/judge identity,
rubric, context budget, failures and token use. Retrieval and end-to-end QA are
separate metrics. A partial run must not publish a full-suite score.

The campaign runner will retain every raw result and its source hashes.
Required suites: LongMemEval-S (500), LongMemEval-V2 Small/Medium, all ten LoCoMo
histories and every question, AMA-Bench, all BEAM sizes including 10M tokens.
Scalability counts are 10K/100K/1M/10M/11M actual memories, not tokens.

Run all full suites and the three local adapters in sequence:

```sh
python eval/campaign.py \
  --data-root /private/tmp/instantkv-official-eval/data \
  --sources /private/tmp/instantkv-official-eval \
  --key-file /private/tmp/instantkv-evaluation-openai.key \
  --budget-file /private/tmp/instantkv-official-eval/api-budget.sqlite3 \
  --output /private/tmp/instantkv-official-eval/results
```

Use the Python environment installed from `requirements.txt`. Prepare the pinned
source repositories and datasets listed in `campaign.json` first. Run the V2
upstream `data/prepare_data.py` script to extract screenshots. The Supermemory
binary path is machine-specific; change that path without changing its recorded
SHA. Results include raw retrieval, model responses, token use, failures, source
hashes, effective settings and an append-only ledger.

Validate the harness with `python -m unittest discover -s eval -p 'test_*.py'`.
The corpus adapters passed synthetic storage and retrieval checks. The Luna
reader and the official LongMemEval judge passed a synthetic end-to-end check.
These checks are not benchmark results.

Each suite runs all questions against fresh corpora, with three retrieval
repetitions and one QA pass per provider. All seven suites contain **7,884 QA
questions per provider**. BEAM includes 100K, 500K, 1M and 10M token histories.
V2 Medium contains 447 distinct question-specific corpora. Full runs can take
many hours. Check `campaign-status.json` and each job log for current progress.

Comparison limits: SQLite runs in process and its RSS includes the Python runner.
Supermemory uses its local v0.0.8 embedding path with extraction, reranking and
query rewriting disabled. This is not a test of its full hosted pipeline.
Unavailable evidence labels produce null retrieval metrics. API and retrieval
errors stay in the score denominator. A budget stop leaves the report incomplete.

Mem0, Zep, Tantivy, an independent dense baseline and record scalability runs
are still pending. Do not treat BEAM's 10M tokens as 10M stored memories.

Check progress and completed scores with `python3 eval/status.py`.
For a live page, run `python3 eval/status.py --serve 8769` and open
`http://127.0.0.1:8769`. It refreshes every ten seconds and reads the current
shared spending ledger. Run reports and raw outputs remain in the results folder.
The displayed ETA covers the current retrieval job only. QA runs after retrieval;
the full queue can take days, especially V2 Medium's 447 separate corpora.

## Faster quality evaluation

`parallel-quality.json` keeps the full questions, source histories, frozen engine,
reader model, judge model and context budget. It uses one retrieval pass and runs
several suites/providers in parallel. Its latency and RAM measurements are under
shared load; they do not support isolated speed or memory-efficiency comparisons.

The parallel profile reuses one fresh Supermemory process per suite, with a fresh
container tag for each corpus. This avoids loading the embedding model hundreds
of times. Corpora stay isolated for queries. RSS and disk are cumulative across
scopes and must be reported that way. It does not change instantKV's engine.

Priorities: full LongMemEval-S, LoCoMo, AMA-Bench and V2 Small. V2 Medium and
BEAM's largest histories are deferred, not shortened or relabelled as full runs.
No score estimate or marketing claim replaces an observed complete result.

Supermemory's fast profile uses batches of 16 for ingestion. All source chunks
must round-trip without changes; the final partial batch is flushed before any
query. Write-latency samples are batch requests, not per-record durable latency.
Interrupted runs stay in the ledger. A fresh full retry gets a new output folder.

## Evidence first and API limits

The account reports 500 requests/minute and 200K tokens/minute for GPT-6 Luna.
The initial parallel QA burst hit that limit. Those QA scores must not be cited
as model quality. Raw failures and interrupted runs are preserved.

`rate.py` shares a conservative 400 RPM / 150K estimated TPM allowance across
processes. It does not change the model, reasoning effort or context budget.
`score_saved.py` reuses all saved contexts for a complete suite. The current
priority is a full 500-question instantKV QA run after the verified retrieval
results. Large suites are deferred; they are not marked complete.

Independently verify the published rankings with an environment that has
`pytrec_eval` installed:

```sh
python eval/verify_saved.py \
  --data-root /private/tmp/instantkv-official-eval/data \
  --results docs/benchmarks/2026-10-04-full-retrieval
```

[The evidence report](../docs/benchmarks/2026-10-04-full-retrieval/README.md)
contains the full dataset counts, scores and comparison limits.
