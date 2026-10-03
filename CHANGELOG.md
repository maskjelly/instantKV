# Changelog

## Unreleased

- Add fixed local retrieval tests for NFCorpus, ArguAna, LoCoMo and a LongMemEval-S pilot.
- Publish raw rankings, rejected/truncated queries, independent scoring and short benchmark notes.

- Add bounded BM25 search with English stemming through Rust, HTTP, CLI and MCP.
- Commit search postings and corpus statistics with record updates, deletion and expiry.
- Backfill older structured memories atomically on first open; preserve record revisions.
- Measure SciFact document recall and rerun existing latency/recovery benchmarks.

- Add `remember`, `recall`, `browse` and `forget` through Rust, HTTP, CLI and MCP.
- Store content, topics, tags, event time and custom JSON metadata.
- Maintain ordered topic/tag/time indexes with record changes in one transaction.
- Limit keyword scan work and response size. Bind cursors to their namespace and filters.
- Require create-only saves or observed revisions for updates. Retrieval requires get and list grants.
- Add five MCP tools, generated schemas, an embedded example and an optional Ollama tool loop.
- Use a smaller default local profile: loopback, private credentials and an 8 MiB redb cache.
- Build and test Linux ARM64 in native CI. Physical-device measurements remain pending.
- Record three 10,000-memory Mac runs and exact recovery of all 30,000 memories after abrupt restarts.
- Use a minimal website with local fonts, grouped guides and expandable diagrams.
- Shorten the README and simplify product, setup and benchmark wording with ASD-STE100 principles.
- Replace the raw KV browser demo with live remember, filtered recall, browse and revision-checked forget.
- Record three current memory-demo runs; preserve query pages, exact reads and verified deletion receipts.
- Update CLI and embedded demos to exercise the current memory lifecycle across a restart.
- Measure exact reads and forget; verify that deleted memories are absent from all browse pages.

Native phone integration, real-model quality evaluation and ARM performance targets remain unverified.

## 0.1.2 — 2026-10-01

- Standard shared knowledge base and private agent namespace terminology across setup, CLI/MCP and documentation.
- Fresh swarm setups use `shared`; existing configurations, data and checkpoint formats remain compatible.

## 0.1.1 — 2026-10-01

- Shared read-only knowledge and private cloud-agent namespaces via per-namespace grants.
- Swarm init profile and a real HTTP isolation, compaction and restart demo.
- Classic desktop artwork, swarm topology, lifecycle and distributed consolidation proposal.
- Quick-start reports the actual Compose port; release downloads show progress and time out.

Single-node sharing works today. Physical replication and automatic consolidation
remain roadmap proposals.

## 0.1.0 — 2026-10-01

- Durable knowledge, RAM scratch with TTL/FIFO, bounded quotas and revision conditions.
- Atomic immutable compaction checkpoints, bounded restore and safe old-bundle pruning.
- Authenticated HTTP, CLI init/doctor/demo/bench and seven MCP stdio tools.
- Docker Compose quick-start, architecture/schema docs, original logo and editable art.

Initial single-node release. Real runtime lifecycle integration, online backups,
retired-session deletion and deeper crash/disk-failure testing remain on the roadmap.
