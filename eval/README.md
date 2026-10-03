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
