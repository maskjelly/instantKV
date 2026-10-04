# Changelog

## Unreleased

- Add `mcp-local`: MCP stdio and an authenticated local server in one Rust process, with persistent storage and shutdown on disconnect.
- Add an OpenCode installer with config backups and automatic memory rules for normal conversations.
- Test native MCP startup, clean stdout, private credentials, restart recovery and revision updates.

- Show measured RAM, query p50/p95/p99, failure counts, writes, startup, storage and throughput beside retrieval scores.
- Highlight native runtime figures and the highest observed quality result for each provider.
- Publish the full native LongMemEval-S GPT-6 Luna QA model variant: 426/500 correct, zero API failures, raw answers and a 95% clustered-bootstrap interval.

- Publish full LongMemEval-S and LoCoMo retrieval results with independently verified rankings.
- Replace the pilot on current public pages. Keep the previous reports as historical evidence.
- Redesign the landing page, benchmark overview and engineering post with report-driven charts and editorial images.
- Remove public demos, recordings, demo navigation and the Worker proxy bindings. Redirect old demo pages to setup; return HTTP 410 for demo API calls.
- Exclude the initial API rate-limit failures from quality claims; preserve the failed runs.

- Add fixed local retrieval tests for NFCorpus, ArguAna, LoCoMo and a LongMemEval-S pilot.
- Publish raw rankings, rejected/truncated queries, independent scoring and short benchmark notes.

- Add bounded BM25 search with English stemming through Rust, HTTP, CLI and MCP.
- Accept ranked queries up to 16 KiB. Select at most 64 original indexed terms and report query reduction.
- Add bounded WAND pruning and optional low-weight related terms. Expansion stays off by default.
- Use compact query fingerprints in ranked cursors. Old ranked cursors require a new search after upgrade; database tables are unchanged.
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
- Earlier prototype: replaced the raw KV browser demo with structured tools; the public demo is now retired.
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
