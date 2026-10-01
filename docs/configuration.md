# Deployment policies

**Implemented:** strict TOML parsing and validation. **Planned:** runtime enforcement.
Unknown fields and unsupported enum values fail, so typos cannot silently change policy.

## Profiles

| Namespace in agent profile | Storage | Lifetime | At capacity |
|---|---|---|---|
| knowledge | durable | No default expiry | Reject writes |
| checkpoints | durable | No expiry in checkpoint service | Reject writes |
| scratch | memory | Default 1 hour; maximum 1 day | Evict oldest |

`local-cache.toml` is a standalone disposable profile; it is not suitable for
compaction handoffs that must survive a server restart.

## Rules and units

- `version = 1`; all sizes are bytes and durations are positive integer seconds.
- Bind addresses are IP:port; IPv6 uses brackets. Disabled authentication requires
  loopback. Port zero is rejected so deployment ports are explicit.
- Relative `data_dir` paths resolve against the working directory.
- `max_request_body_bytes` bounds the incoming raw value body. Namespace
  `max_value_bytes` cannot exceed it. HTTP control-envelope overhead gets its own
  bounded endpoint allowance during server implementation.
- `max_in_flight_requests` bounds active requests; `request_timeout_seconds` is
  the response deadline, not a guarantee that an admitted commit was cancelled.
- `cleanup_interval_seconds` schedules sweeps; `cleanup_batch_entries` bounds
  deletions per batch. A one-second interval does not guarantee physical deletion
  within one second under backlog or disk failure.
- Quotas count entries and stored key + value bytes. They need headroom for process
  metadata and database indexes; they are not RSS or physical disk limits.
- Namespaces and principals must have unique names of 1–64 ASCII letters, digits,
  `_` or `-`. Permissions name existing namespaces and explicit operations.
- `value_kind`: `bytes` accepts arbitrary bytes; `utf8` requires valid UTF-8;
  `json` requires valid JSON. Memory/checkpoint APIs add their own envelope checks.
- `on_full = "reject"` preserves existing data. `evict_oldest` is memory-only FIFO.
  Reads and overwrites of a live entry do not change its insertion order.

## TTL resolution for ordinary records

1. Explicit request TTL takes precedence; zero and overflow are errors.
2. Otherwise apply `default_ttl_seconds`, if present.
3. If still absent and `require_ttl = true`, reject the write.
4. Otherwise the record has no expiry.
5. If a maximum exists, reject TTLs above it; do not silently clamp.

`max_ttl_seconds` requires `require_ttl = true` to prevent immortal writes bypassing
the maximum. A default cannot exceed the maximum. Checkpoints have no TTL; their
future endpoint rejects a namespace configured with expiry.

## Credentials

The agent profile names `INSTANTKV_APP_TOKEN` and `INSTANTKV_READER_TOKEN`; it
contains no token values. The planned server reads unique nonempty high-entropy
secrets at startup and fails if missing/duplicated. `check-config` only checks
environment-variable names and grants; it never reads secrets.

The sample writer can access all three namespaces. The reader can only get/list
knowledge. Namespace permissions apply equally to HTTP, CLI, and MCP calls.
Per-agent labels are metadata; private agents need separate namespace scopes.

First release loads configuration at startup; changing it requires restart.
Persisted namespace mode changes/removal must fail until an explicit migration
or deletion is performed. Lowered quotas block growing writes without auto-deleting
durable data. New TTL policies apply to new writes, not retroactively to old data.
