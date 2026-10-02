# Verified build checkpoints

## 1 — Foundation

Rust workspace, strict deployment policy, architecture, and example profiles.
Six configuration tests, formatting, and strict Clippy passed before the first push.

## 2 — Durable memory core

Implemented memory and redb backends, atomic quota accounting, conditional
revisions, indexed expiry, FIFO scratch eviction, immutable checkpoints with
transactional latest pointers, and bounded restoration with reference status.

Seventeen tests passed. Strict Clippy passed for the core. Checks include durable
reopen, rollback when a checkpoint pointer exceeds quota, idempotent retries,
monotonic cache expiry, and exactly one successful competing conditional writer.

The network/client layer is the next checkpoint; no throughput claim yet.

The initial core-only push exposed a Cargo.lock/manifest mismatch in Linux CI.
The following server checkpoint synchronized the manifests and lockfile; CI passed.

## 3 — HTTP, CLI, and real restart demo

Authenticated HTTP routes, exact recall, prefix metadata pages, scoped API keys,
ETags, bounded request execution, graceful shutdown, setup/doctor commands, and
a closed-loop HTTP benchmark client.

Twenty-two tests passed, including five HTTP/authentication tests. Strict Clippy
passed. The demo saved a checkpoint, cleared simulated agent context, killed its
server process, reopened the database, and recovered the capsule and knowledge
through HTTP. Scratch memory was empty after restart.

## 4 — Agent tools

Six MCP stdio tools using the official Rust SDK, JSON/binary-safe recall, typed
checkpoint schemas, and agent setup instructions. Twenty-three tests passed;
the MCP integration test negotiates protocol, discovers tools, parks knowledge,
saves/restores a checkpoint through authenticated HTTP, and verifies visible tool errors.

## 5 — Checkpoint retention

Added atomic deletion of old checkpoints through HTTP, CLI, and MCP. The current
latest checkpoint is protected from deletion. Fixed FIFO order when an expired
entry outside the cleanup batch is recreated. Twenty-five tests and strict Clippy
passed; pruning also verifies quota reclamation and restore after reopening.

## 6 — Repeatable packaging

Added non-root Docker deployment, a short Compose CLI wrapper, offline backup
helper, checksummed binary packaging/installation, and Linux/macOS CI with
portable Linux and container checks. Auth now classifies the matched route rather
than a record key suffix. Local tests, Clippy, shell syntax and generated-schema
consistency passed. Remote container/backup/benchmark evidence follows separately.

## 7 — Verified deployment, measured performance and documentation

Rove's Docker quick-start and real kill/restart demo passed. The offline backup
drill exposed host copy ownership loss; backups now stream a tar archive, and an
isolated restore helper verified the known checkpoint. Benchmark profiles ran
three times each: 157,500 measured requests, zero errors. Raw JSON, tested code
revision, binary/image hashes and shared-host load conditions are committed.

The usable deployment receives a separate volume from the disposable benchmark
instance. Added bounded checkpoint stdin/file input (tested through the CLI),
original editable logo/architecture, current setup/API/policy/operations docs,
contribution/security guidance and issue templates. Twenty-six local tests and
strict Clippy passed. Linux/macOS/container CI includes demo, schema and backup gates.

## 8 — Published binaries and final setup polish

Published v0.1.0 as an early release from verified commit `3005ec7`, with Linux
x86_64 static-musl and macOS arm64 archives, checksums and build metadata. The
published downloads passed the demo on both macOS and Rove. On Rove the first
release-based setup took 281 seconds, primarily download time, without compiling.

Fixed the ready address when a custom host port is supplied through `.env`;
CI now checks that case. Installer downloads show progress and have bounded
timeouts. Added SSH MCP instructions; the usable VPS checkout is
`/srv/instantkv/app`, separate from the retained benchmark state.
## 9 — Cloud agents and classic desktop identity

Runtime checkpoint `b8f768b`: 28 local tests, formatting, strict Clippy, both HTTP
demos and all three configuration profiles pass. The new test proves shared
shared knowledge reads, private writes, forbidden sibling/shared operations, rejected
out-of-scope checkpoint references, and forbidden reference status during restore.
Linux and macOS native CI checks also passed. Its container job stopped at the
new port-output assertion because `rg` is absent from the runner; the assertion
now uses portable `grep`. Full container validation is rerun after this fix.

Visual checkpoint `b76bca4`: original square pixel memory-disk logo, classic
desktop wordmark, four PNG diagrams and matching editable sources are published.
The deployed GitHub README was inspected in a real Chromium browser: all eight
images including badges loaded; a 390px mobile viewport had no horizontal
overflow. All local document links and image paths resolve. Future distributed
replication and consolidation are visibly marked as proposals.

Rove's published 0.1.0 instance separately passed a real seven-tool MCP session
over SSH: park, get, checkpoint and restore with an available knowledge reference.
Its saved `rove-first-checkpoint` was then restored from a fresh offline backup
into an isolated volume before upgrading. Server credentials and backup contents
are private and are never committed.

Rove also passed the 0.1.1 swarm init, doctor, two-agent demo, shared knowledge
recall, private checkpoint save and restore using the Linux artifact from runtime
checkpoint `b8f768b`. The swarm has its own volume and loopback port 8096. A fresh
offline swarm backup restored `alpha-first-handoff` from `alpha_checkpoints` in an
isolated volume. This exposed the restore helper's single-agent namespace default;
it now accepts an optional namespace, and CI verifies both profiles' backup drills.

## 10 — Verified 0.1.1 release and request audit

Release target `ec29901` passed [all Linux, macOS and Docker CI jobs](https://github.com/maskjelly/instantKV/actions/runs/36878075700),
including 28 tests, both demos, three config profiles, schema/script checks and
both single-agent and private-agent backup drills. Checksummed Linux static-musl
and Apple Silicon macOS archives record that exact commit in BUILD.txt.
[0.1.1 is published as an early prerelease](https://github.com/maskjelly/instantKV/releases/tag/v0.1.1).
The published installer downloaded and checksum-verified both platform packages;
their installed binaries passed `demo --swarm` on macOS and Rove Linux.

Both Rove instances now run the release binary: original profile on loopback
8095 and shared/private swarm on 8096. The old `rove-first-checkpoint` and its
knowledge reference survived upgrade; `alpha-first-handoff` remains restorable.
Scoped Alpha MCP discovered seven tools, read shared knowledge, stored private knowledge,
saved/restored its capsule, and received 403 for shared writes and sibling access.
A 2,000-request Alpha GET smoke run completed with zero errors; the earlier
three-run benchmark reports retain their own measured commit and conditions.

[The request audit](request-audit.md) checks every prompt and distinguishes
implemented sharing from future replication/consolidation/quality metrics.

## 11 — Monolith visual identity

The latest minimal metallic brief supersedes the classic desktop theme. Monolith
uses an original split chrome K, graphite/silver palette, Space Grotesk, square
surfaces and fine connectors. The wordmark, icon and four diagrams were rendered
and visually inspected; matching Tesseract sources retain editable text/shapes
and licensed fonts. The transparent SVG shares the mark's geometry and reflections.

The README, asset index, theme rules, changelog and request audit follow this
direction. Implemented and future behavior remain explicitly labeled. This
checkpoint changes artwork/documentation and leaves the published 0.1.1 runtime
verification target intact.

Visual checkpoint `84310a6` is committed and pushed. The deployed GitHub README
was inspected in Chromium at 1440px and 390px: all eight images loaded with the
new asset dimensions; the mobile page width stayed at 390px. Local Markdown
links, PNG/source archive dimensions, renderer syntax and `git diff --check`
also passed.

## 12 — Cloudflare website and public documentation

Built an Astro/TypeScript static site in `site/` using the Monolith identity.
The homepage targets self-hosted cloud agents; a pausable scrolling banner states
that managed hosting is in development. The site renders existing repository
Markdown directly and adds feature, CLI, HTTP and website-operation guides.
The benchmark page computes medians/totals from all 15 original reports, retains
their measured revision/conditions and provides throughput/latency controls and
raw downloads. Pagefind search is browser-local; `llms.txt` and `llms-full.txt`
provide machine-readable documentation.

Local validation: strict Astro checks, 26-page build, all local rendered links,
anchors/assets, benchmark report totals, search index and Wrangler dry-run pass.
Chromium checks cover 1440px/390px layouts, chart controls, search/no-result state,
verified clipboard contents, mobile docs navigation, announcement pause, reduced
motion and custom 404. External script bundles resolve the CSP issue caught by
browser QA. Publication and live HTTPS verification are recorded separately below.

## 13 — Public domain and live site verification

`https://instantkv.com` is published on Cloudflare Workers Static Assets. The
deployment from `bbbd22b` is version `6b551971-aeba-44ce-9a3a-d29ac83b7c44`;
[website CI passed](https://github.com/maskjelly/instantKV/actions/runs/36890922820).
The apex Custom Domain is attached, authoritative/public DNS resolves to
Cloudflare, and Rove fetched the homepage through normal DNS with valid HTTPS.
The optional `www` hostname has an externally managed DNS conflict and was
excluded. Publishing the apex succeeded without changing that record.

Live Chromium checks passed at 1440px/390px: homepage, quick start, feature/HTTP
and contributor docs, benchmarks, images and overflow checks. Throughput/p50/p99
controls, search/no-result state, verified clipboard contents, mobile docs menu,
announcement pause/play, reduced motion and custom 404 work. Live QA also caught
Cloudflare's automatically injected analytics beacon; the CSP now permits its
documented hosts. Final live checks report zero JavaScript/CSP errors and verify
machine-readable docs, raw benchmark downloads and sitemap responses.

GitHub's repository homepage points to the site. Documentation/benchmark pages
require no account. The memory node remains self-hosted; managed hosting is
explicitly in development, with no promised date or price. Deployment is manual
through the checked-in command; automatic Workers Builds integration still needs
the account's separate Builds permission/Git connection. No interactive OAuth
credentials were copied into GitHub secrets.

## 14 — Standard terminology and verified 0.1.2 release

Runtime checkpoint `6eceb8b` changes the fresh swarm namespace to `shared` and
uses shared knowledge base/private agent namespace terminology. Existing namespace
names remain valid; persisted namespaces are not silently renamed. Documentation,
GitHub description, website and all four editable architecture diagrams follow
the same vocabulary.

[Release CI passed](https://github.com/maskjelly/instantKV/actions/runs/36893404728):
28 invariant tests, strict Clippy/formatting, Linux/macOS demos, Docker setup,
restart and backup drills. Checksummed [0.1.2 prerelease artifacts](https://github.com/maskjelly/instantKV/releases/tag/v0.1.2)
record the exact runtime source commit. The published installer and swarm demo
passed on macOS and Rove Linux. Existing 0.1.1 agent volumes were preserved;
the isolated public demonstration uses 0.1.2.

## 15 — Live Cloudflare memory demonstration

Website/runtime integration checkpoint `17c2bf3` is committed and pushed;
[website CI](https://github.com/maskjelly/instantKV/actions/runs/36897862088) and
[Rust/Docker CI](https://github.com/maskjelly/instantKV/actions/runs/36897862154)
passed. Cloudflare deployment `2565000a-fd33-4ee9-9fb9-ae6703f6c4ff` serves
[the public demo](https://instantkv.com/demo/). The Worker reaches an isolated
Rust container through a private Workers VPC service and QUIC Tunnel. The
coordinator generates bounded synthetic batches and reuses backend HTTP connections;
every acknowledged value is actually stored and fetched through instantKV.

Real HTTPS Chromium verification wrote 100,000 cache records (68.25 MiB) and
10,000 immediate-durable records (6.82 MiB), with zero failed API requests or
browser errors in both runs. Exact first/middle/last cache reads, pause/resume,
writer-context clearing, independent-tab recall and 390px mobile layout passed.
Durable record 9,999 was exactly verified after clearing context. Homepage,
quick start, benchmark page, live-demo documentation and search also passed.
[Raw reports and measurement boundaries](live-demo.md#recorded-live-verification)
keep these single public demonstrations separate from controlled benchmarks.

Seven coordinator/proxy tests cover exact integrity, credentials, body/route
limits, partial failure/retry, connection reuse, response bounds and redirect
rejection. Static checks/build verify 28 HTML pages, 22 documentation guides,
rendered links/assets, search and the original 15 benchmark reports. The new
editable SVG explains the public and private storage path in the README and
guide. Upstash, Turso and Valkey were reviewed before the demo design; Monolith
retains its own identity. Demo data expires after 15 minutes. Managed hosting
and distributed consolidation remain future work.

## 16 — Copy review and product comparison

Reviewed the README, website and documentation for stale status, unclear terms
and stiff wording. The features guide now names 0.1.2 and explains that the live
demo uses temporary records while managed hosting is still being built. Setup
guidance distinguishes the prebuilt binary from a Rust source build. The README
and onboarding explain keys, namespaces and checkpoints before using them.

An independent read-only review found four phrases worth tightening; those were
revised. [Why instantKV](choosing-instantkv.md) compares the service with Mem0,
Graphiti, Letta, Upstash and Valkey using official documentation checked on
2026-10-01. It explains when each fits and keeps performance claims tied to the
recorded workloads. No competitor speed or cost ranking is claimed.

Local validation passed: formatting, Astro/TypeScript checks, seven gateway/proxy
tests, a 29-page build, all rendered links/anchors/assets, the search index,
machine-readable docs and the original 15 benchmark reports. Rust storage and
wire formats are unchanged.

Wrangler preview checks passed at 1440px and 390px: homepage, comparison, features,
setup, benchmark and demo pages stayed within the viewport. Search and benchmark
controls worked. Another 1,000 real cache writes completed with zero errors;
the writer was cleared, record 999 was verified, and an independent tab retrieved
record 500 with the expected text. Screenshots of the homepage and mobile guide
were inspected before publishing.

## 17 — Historical branches and measured Mac replay

Expanded the distributed proposal with historical snapshot forks, independent
agent branches, findings submitted during runs, reviewed shared updates and
peer awareness. The schema specifies lineage, batch sequences, replayable event
IDs, cursor recovery and stale-peer leases. The README and roadmap label these
features as planned; the new SVG shows the proposed flow.

Ran the unchanged demo coordinator against the published 0.1.2 Rust binary on an
Apple M4 Pro / 24 GiB Mac. Three 100,000-record RAM runs and three 10,000-record
durable runs completed with 330,000 acknowledged writes, 24 exact reads and zero
errors. Median throughput runs: 42,517 RAM writes/s and 225 durable writes/s.
Full raw operation timings, hardware, binary hash, conditions and reproduction
are published. The Mac durable result is slower than the earlier VPS demo;
both datasets stay visible.

The default website demo now replays the median run at 2× animation speed and
caches four real GET responses per mode. It labels cached lookup time separately
from recorded backend time. Whole-run throughput and percentiles stay measured;
no numbers receive an artificial performance uplift. Live VPS still performs
actual writes and independent reads.

Local validation: formatting and Astro/TypeScript checks, nine coordinator,
proxy and recording-integrity tests, 29-page build, rendered links/assets/search,
all 15 original benchmark reports and six new recordings. Chromium preview
passed cache/durable replay, pause/resume, all saved samples, context clearing,
independent recorded reader, 390px layout and zero replay API calls. A further
1,000 live VPS writes and exact reads in two independent tabs passed with zero
browser errors. The separate in-progress visual redesign was preserved.

Production Chromium verification passed the same recorded and live workflows at
`https://instantkv.com`, including exact unscaled metrics, cached samples,
independent reader tabs and 390px layout, with zero browser errors. A final
startup fix keeps the replay button disabled until its recording is loaded and
enables the live button only after its handlers are ready.

## 18 — White technical blueprint website

Rebuilt the website around the later white blueprint brief. White paper, blue
ink, square controls, drafting grids and original SVG diagrams replace the dark
metal layout. The flat blue split-K preserves the mark's shape. The homepage
explains self-hosted agent memory, publishes actual Mac measurements and gives
working installation commands. Setup, demo, benchmarks and docs are direct
product paths. Managed hosting and distributed branches remain clearly planned.

The same theme now covers all 29 pages. Mobile gets a complete compact swarm
diagram; wide technical figures scroll without widening the page and can receive
keyboard focus. The native HTML/CSS layout needs no WebGL renderer. The docs
stay sourced from repository Markdown, with locally served fonts and search.

Local checks passed: formatting, Astro/TypeScript, nine coordinator/proxy/recording
tests, the static build, every rendered local link/anchor/asset, search and raw
benchmark downloads. Chromium checked nine page types at 1440, 390 and 320px,
including white rendering with a dark system preference, code copying, search,
chart controls, keyboard navigation and the custom 404. No browser errors.

Recorded cache/durable replay, pause/resume, eight exact saved responses,
cleared context and an independent recorded reader passed. Recorded mode made
no live API calls. A further 1,000 live VPS writes and exact reads in independent
tabs also passed. Homepage Lighthouse scores on the local Worker preview were
100 for performance, accessibility, best practices and SEO; demo performance
was 99, with 100 in the other categories. These are local checks, not a public
latency claim. Screenshots were inspected before publication.
