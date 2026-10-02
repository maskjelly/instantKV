# Changelog

## Unreleased

- Structured local-memory MVP: remember, recall, browse and forget through Rust, HTTP, CLI and MCP. Topics, tags, explicit event times and custom JSON metadata.
- Atomic ordered time/topic/tag indexes maintained alongside record updates, replacement, deletion and expiry cleanup. Bounded literal keyword filtering with filter-bound cursors.
- Configurable candidate, scan-byte and serialized-response limits. Create-only saves and revision-protected edits/deletes; queries require both get and list grants.
- Four new MCP tools alongside the seven existing KV/checkpoint tools. Generated memory schemas, embedded Rust example and optional Ollama tool loop.
- Smaller default local profile with loopback access, private credentials and an 8 MiB database cache. Linux ARM64 build/installer path; device validation pending.
- Three 10,000-memory Mac runs with raw latency/RSS evidence and exact recovery after abrupt restart. Native mobile integration and ARM performance targets remain planned/unverified.
- Minimal Astro website: neutral surfaces, locally served Geist, simpler docs and expandable diagrams. Homepage and benchmarks emphasize the source MVP, measurements and next milestones.
- Existing live KV demo, recorded Mac replay, benchmark controls and browser-local search retained. That demo measures raw KV workloads rather than the new memory API.

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
