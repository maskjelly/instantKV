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
