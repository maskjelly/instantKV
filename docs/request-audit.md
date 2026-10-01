# Session request audit

Reviewed against every user prompt in this session, 2026-10-01.
The current runtime/release target is `6eceb8b` (0.1.2); its
[Linux/macOS/Docker CI passed](https://github.com/maskjelly/instantKV/actions/runs/36893404728).
The [0.1.2 prerelease](https://github.com/maskjelly/instantKV/releases/tag/v0.1.2)
contains checksummed Linux x86_64 and Apple Silicon macOS binaries. Published
installer downloads, checksum verification and the swarm demo passed on macOS
and Rove Linux. Existing Rove agent deployments retain 0.1.1 and their data;
the isolated public demo runs 0.1.2. Fresh swarm setups use `shared`.

| Request | Result and evidence |
|---|---|
| Set up the README requirements; recommend a stack and architectural plan | Rust + Tokio + Axum + redb + TOML selected and implemented. [Architecture and trade-offs](architecture.md); [configuration policies](configuration.md). |
| Agent memory KV: park before compaction, restore afterward, recall parked knowledge | Durable exact-key records, immutable capsules, atomic latest pointers, bounded restore and versioned references. [Contract](agent-memory.md), [lifecycle diagram](assets/lifecycle.png), [MCP tools](agents.md). |
| Excellent DX, simple self-hosting, quick setup and working demo | One binary/config/data directory; generated private credentials; checksummed binaries; non-root Docker; init/doctor/CLI/MCP. Both real-HTTP restart demos pass. [Quick setup](quickstart.md), [demo](demo.md). |
| Benchmark it and use Rove to test it | 15 raw reports, three runs per workload, 157,500 successful measured requests and zero errors; hardware/source/load recorded. Rove additionally passed the swarm demo, scoped MCP calls, two profile backup drills and a 2,000-request swarm smoke benchmark with zero errors. [Benchmark evidence](benchmarks.md), [operations](operations.md). |
| Good logo and architecture images visibly in the README | Original Monolith logo and wordmark at the top; swarm, lifecycle, storage/schema and distributed diagrams embedded. PNGs and editable source pairs are [listed here](assets/README.md). |
| Authentic old desktop visuals: low resolution, square corners, early Windows/Linux feel | Delivered in visual checkpoint `b76bca4` and inspected in Chromium: eight images loaded, no horizontal overflow at 390px. Superseded by the later Monolith design request below; history preserves the original artwork. |
| Own super minimal metallic, chromatic, monolithic theme | Visual checkpoint `84310a6`: original split chrome K, graphite/silver palette, Space Grotesk, square geometry and restrained reflections. Logo, wordmark, all four diagrams, README badges and [theme guide](assets/README.md) use Monolith. Editable sources and font licenses are included. Deployed Chromium check: all eight images loaded; no page overflow at 390px. |
| Hosted website, startup/usage guides, feature and contributor docs | [instantkv.com](https://instantkv.com) is live with 28 static pages, including 22 guides rendered directly from repository Markdown. [Quick start](https://instantkv.com/docs/quickstart/), [features](https://instantkv.com/docs/features/), CLI/HTTP/MCP, configuration, operations and [contributing](https://instantkv.com/docs/contributing/) are published with local search and agent-readable Markdown. |
| Best-fit Cloudflare stack and purchased domain | Astro + TypeScript + Workers Static Assets implemented; Pagefind search. Active Cloudflare apex Custom Domain and HTTPS verified in Chromium and from Rove. [Deployment runbook](website.md); [live evidence](checkpoints.md). Optional `www` is excluded because of an existing managed DNS conflict. |
| Benchmark page and confident speed/efficiency/cost positioning | [Interactive benchmark page](https://instantkv.com/benchmarks/) calculates medians/totals from all 15 raw reports and publishes download links, conditions, tails and reproduction commands. Homepage leads with 4,010 reads/sec, 10.3 MiB observed post-run memory and $0 MIT software license fee; infrastructure cost and measurement scope stay explicit. |
| Self-hosted service positioning and scrolling future-hosting announcement | No SaaS signup or live managed API claim. Pausable scrolling banner says managed hosting is in development; reduced-motion mode is static. [Roadmap](roadmap.md) defines the future service and launch gates without invented dates/prices. |
| Market specifically to remote cloud agents and swarms | README opening, brand tagline, GitHub description/topics and [cloud-agent guide](cloud-agents.md) center this audience and workflow. |
| Shared knowledge given to every agent; independent private namespaces | Working swarm profile: read-only `shared` for agents; private `alpha`/`beta` records and checkpoint scopes; operator publishing. Per-namespace permissions enforce the boundaries. The guide shows how to repeat the pattern for more agents. [Shipped profile](../config/swarm.toml), [swarm diagram](assets/swarm.png). |
| Future distributed memory and end-of-run knowledge consolidation | Complete proposal: versioned baseline replicas, private overlays, shareable completion deltas, durable jobs, source validation, deduplication, conflict review, conditional publication and pull sync. Knowledge quality metrics track sources, freshness and evaluated recall. [Design/schema/rollout gates](distributed-memory.md), [roadmap](roadmap.md). |
| Learn from strong database/KV/low-level and KDE repositories | Primary references and adopted practices documented for Valkey, TigerBeetle, redb, KDE KCoreAddons/ECM and the official Rust MCP SDK. [Engineering references](inspirations.md). |
| Proper open-source repo descriptions, docs and good practices | MIT license, contribution/security guides, private vulnerability reporting, issue/PR templates, pinned CI actions, locked dependencies, strict configuration, invariant tests, changelog and deployment/backup docs. [Contributor guide](../CONTRIBUTING.md), [security](../SECURITY.md). |
| Commit and push each checkpoint/stage | Foundation, storage, HTTP/DX, MCP, retention, packaging, benchmark/docs, identity, swarm grants, CI portability and private backup fixes were committed and pushed. [Checkpoint history](checkpoints.md) and Git history record the stages. |
| Continue independently with permission; edit files directly | Project changes made directly with file edits. The renderer is reproducible artwork tooling; protocol clients and benchmarks verify behavior. No edit-application scripts or external messaging were used. |
| Revisit all prompts after completion | This audit checks every requested area and distinguishes shipped behavior from explicitly requested future planning. |
| Use standard industry terminology throughout | Shared knowledge base, private agent namespace, canonical baseline and knowledge quality metrics replace project-specific branding in config, docs, website, diagrams and GitHub description. Existing namespace names are retained for compatibility. |
| Host a compelling live demo on Cloudflare; independent input/output with real latency | Public Worker/Static Assets plus private Workers VPC and QUIC Tunnel to an isolated Rust instance. Verified 100,000 cache records/68.25 MiB and 10,000 durable records/6.82 MiB, zero failed requests, pause/resume, cleared writer context, independent-tab recall, exact reads and mobile layout. [Demo and measurement boundaries](live-demo.md), [cache report](demo-results/2026-10-01-cloudflare-cache.json), [durable report](demo-results/2026-10-01-cloudflare-durable.json). |
| Review comparable service sites before committing the design | Upstash, Turso and Valkey reviewed for setup, code/architecture and documentation patterns. Original Monolith theme retained; homepage/nav lead to a working demo. [Design references](live-demo.md#website-design-references). |

## Shipped behavior versus future work

Shared knowledge access plus private namespaces works on one server. A worker does
not receive a physical database fork or an immutable multi-key baseline yet.
Those replicas, automatic completed-run consolidation and knowledge quality metrics
are explicitly proposed, exactly as requested for future planning.

The demos simulate prompt-context clearing while using real HTTP, real process
kill/restart and real persistence. Scoped MCP calls were also exercised on Rove.
A model-runtime hook and real-model recall evaluation are not claimed.

The older multi-run benchmark records its own tested commit and conditions;
it is not relabeled as a distributed or 0.1.1 capacity result. Fault-injection
coverage beyond the current invariants/restart/backup tests remains on the roadmap.
