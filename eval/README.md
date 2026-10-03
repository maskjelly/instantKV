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
