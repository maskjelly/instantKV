# Deployment policies

Strict TOML parsing and runtime enforcement are implemented. Unknown fields,
unsupported enum values, contradictory policies and duplicate grants fail.
`instantkv check-config --config PATH` validates structure without reading secrets
or opening storage. `instantkv doctor` also checks the local setup and live health.

## Profiles

| Agent namespace | Purpose | Storage | Retention | Full |
|---|---|---|---|---|
| knowledge | records | durable | none by default | reject |
| checkpoints | checkpoints | durable | no TTL | reject |
| scratch | records | memory | default 1h, max 1 day | evict oldest |

[Agent profile](../config/instantkv.example.toml) and
[disposable loopback cache](../config/local-cache.toml) are checked in CI.
`init` copies the agent profile and changes the data directory to `.instantkv/data`.

## Rules and units

- Version is `1`. Sizes are bytes; duration fields are positive integer seconds.
- Bind uses IP:port, with brackets for IPv6. Disabled auth requires loopback.
- Relative storage paths resolve against the process working directory.
- `max_request_body_bytes` bounds the entire HTTP body, including checkpoint JSON.
  Namespace `max_value_bytes` must fit that bound.
- `max_in_flight_requests` bounds active requests and submitted blocking work;
  `request_timeout_seconds` bounds the response wait, not commit execution.
- Cleanup interval schedules work. Batch size bounds each memory namespace sweep
  and the shared durable sweep; backlog may delay physical removal.
- Quotas count stored key + value bytes and entries, not RAM or disk size.
- Namespace/principal names use 1–64 ASCII letters, digits, `_` or `-`.
- `purpose = "records"` is the default. `checkpoints` requires durable mode,
  JSON admission, no TTL and rejection at capacity.
- `value_kind = "bytes" | "utf8" | "json"` checks ordinary value format.
- `on_full = "evict_oldest"` is RAM-only FIFO; reads/live overwrites do not reorder.
- Generic keys starting `__` are reserved. Record key limits apply after decoding.

## TTL resolution

1. Explicit request TTL, otherwise namespace default.
2. Missing TTL is rejected if `require_ttl = true`; otherwise no expiry.
3. TTL above a configured maximum is rejected, never silently clamped.

Maximum TTL requires `require_ttl = true`, preventing immortal bypasses.
Memory expiry uses a monotonic clock; durable expiry uses UTC across restarts.
Expired rows are unreadable but count toward quota until cleanup/replacement.

## Credentials and changes

The template refers to `INSTANTKV_APP_TOKEN` and `INSTANTKV_READER_TOKEN`.
`init` generates unique high-entropy tokens in `.instantkv/credentials.env`
(private permissions on Unix). Environment values override saved secrets.
Missing, duplicate or shorter-than-32-byte token values refuse server startup.
The reader can get/list knowledge; the app can access all three namespaces.

Clients use `INSTANTKV_TOKEN`, then `INSTANTKV_APP_TOKEN`, then the app token in
their secrets file. `--secrets-file PATH` supports a different setup. No token
argument is accepted. MCP uses the same client and authorization.

Changes require restart. Existing persisted namespace removal or mode/purpose
changes require migration and are refused. Lowered quotas reject writes while
usage remains over the new limit, including shrinking writes that still exceed it;
explicit deletion can reclaim space. TTL policy changes affect new writes only.
