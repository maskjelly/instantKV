# Bounded search improvement plan

Status: implementation in progress. Frozen before the new benchmark run.

1. Accept up to 16 KiB of query text. Tokenize the whole question. Score at most 64 original terms. For longer queries select terms by corpus rarity and square-root query frequency. Keep a SHA-256 query fingerprint in cursors.
2. Replace term-by-term partial sums with document-at-a-time WAND. Use conservative BM25 upper bounds. Bound decoded postings and iterator reads by the existing 20,000 budget. Keep record, byte and output limits. Report term reduction separately from scoring truncation.
3. Add optional, model-free expansion. A fixed generic English synonym list contributes at most eight terms at one-quarter weight. Apps can supply up to eight expansion terms. Expansion is off by default; do not infer stance or claim semantic understanding.
4. Verify pruned rankings against an independent exhaustive scorer on synthetic held-out corpora. Rerun full ArguAna and the other fixed retrieval datasets. Publish default and expansion results, including losses, reduced queries, truncation, RAM and latency. Reuse frozen Supermemory results as historical controls; do not call them fresh runs.

No benchmark evidence labels select terms or expansion words. No model call or cloud dependency is added.
Phone performance and full answer-quality evaluation remain unverified.
