# Deployment policies

Configure namespaces, storage limits and permissions in TOML. The server rejects
unknown fields, unsupported values, contradictory policies and duplicate grants.
`instantkv check-config --config PATH` validates structure without reading secrets
or opening storage. `instantkv doctor` also checks the local setup and live health.

## Profiles

| Agent namespace | Purpose | Storage | Retention | Full |
|---|---|---|---|---|
| knowledge | records | durable | none by default | reject |
| checkpoints | checkpoints | durable | no TTL | reject |
| scratch | records | memory | default 1h, max 1 day | evict oldest |

[Agent profile](../config/instantkv.example.toml),
[swarm profile](../config/swarm.toml), and
[disposable loopback cache](../config/local-cache.toml) are checked in CI.
`init` copies the smaller [local profile](../config/local.toml), with an 8 MiB
database cache, 4 MiB logical scratch budget and 32 in-flight requests.
`init --profile agent` retains the larger agent profile; `init --profile swarm`
creates a shared namespace, Alpha/Beta private knowledge and separate checkpoint namespaces. All use
`.instantkv/data` and generate credentials for every configured principal.

## Rules and units

- Version is `1`. Sizes are bytes; duration fields are positive integer seconds.
- Bind uses IP:port, with brackets for IPv6. Disabled auth requires loopback.
- Relative storage paths resolve against the process working directory.
- Optional `storage.cache_size_bytes` sets a positive redb page-cache budget.
  It does not cap total RSS; omitted values retain redb's default.
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

## Structured memory query budgets

The source MVP adds optional `[memory]` settings. Older configs use the same
defaults; new local setups include them explicitly:

```toml
[memory]
max_candidates = 1000
max_scan_bytes = 4194304
max_result_bytes = 65536
```

Candidate cap: 1–100,000. Encoded-record scan bytes: 64 KiB–64 MiB. Serialized
response cap: 1 KiB–1 MiB. Each request supplies `limit` (1–100) and `max_bytes`
(default 16 KiB, at most the configured cap). A low configured output cap requires
clients to lower their request budget too. These caps bound work/output, not total
RAM. The full memory JSON counts toward logical quotas; index overhead is extra.

Shape limits: 16 KiB content, 8 KiB metadata, eight tags. Retrieval needs both
`get` and `list`; metadata-only list permission cannot read values through the
memory API. [Query contract](memory-mvp.md).

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

In the swarm profile the operator can access all five namespaces. Each agent can
get/list `shared`, and read/write/delete/list/stats its own knowledge and checkpoint
namespaces. This is one shared server with isolated namespaces; it creates no
physical replica. See [cloud-agent setup](cloud-agents.md).

Use either `namespaces` + `operations` (the same operations on every namespace),
or explicit per-namespace `grants`. Mixing them is rejected:

```toml
[[auth.principals]]
name = "alpha"
token_env = "INSTANTKV_ALPHA_TOKEN"
[[auth.principals.grants]]
namespace = "shared"
operations = ["get", "list"]
[[auth.principals.grants]]
namespace = "alpha"
operations = ["get", "put", "delete", "list", "stats"]
```

Add a separate checkpoint grant as in the shipped swarm profile. Checkpoint saves
require GET permission on every referenced namespace. Restore checks the current
GET grants and reports `forbidden` for references whose access was removed.
The global metrics endpoint requires a stats grant in at least one namespace;
it exposes aggregate service counters, not an agent-specific view.

Clients use `INSTANTKV_TOKEN`, then `INSTANTKV_APP_TOKEN`, then the app token in
their secrets file. `--secrets-file PATH` supports a different setup. No token
argument is accepted. MCP uses the same client and authorization.

Changes require restart. Existing persisted namespace removal or mode/purpose
changes require migration and are refused. Lowered quotas reject writes while
usage remains over the new limit, including shrinking writes that still exceed it;
explicit deletion can reclaim space. TTL policy changes affect new writes only.
