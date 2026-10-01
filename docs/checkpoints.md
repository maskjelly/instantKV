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
# 0.1.1 cloud-agent and visual verification

Runtime checkpoint `b8f768b`: 28 local tests, formatting, strict Clippy, both HTTP
demos and all three configuration profiles pass. The new test proves shared
mother reads, private writes, forbidden sibling/mother operations, rejected
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
