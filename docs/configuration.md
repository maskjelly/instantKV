# Deployment policies

TOML sets the namespaces, storage limits and permissions.
The server rejects unknown fields, unsupported values, conflicting policies and duplicate grants.
`instantkv check-config --config PATH` validates the configuration without reading secrets or opening storage.
`instantkv doctor` also verifies the local setup and server health.

## Profiles

| Default local namespace | Purpose     | Storage | Retention                 | Full         |
| ----------------------- | ----------- | ------- | ------------------------- | ------------ |
| knowledge               | records     | durable | none by default           | reject       |
| checkpoints             | checkpoints | durable | no TTL                    | reject       |
| scratch                 | records     | memory  | default 5 min, max 1 hour | evict oldest |

The [local](../config/local.toml), [agent](../config/instantkv.example.toml),
[swarm](../config/swarm.toml) and [cache](../config/local-cache.toml) profiles are checked in CI.
`init` selects the local profile: an 8 MiB database cache, 4 MiB scratch quota and 32 active requests.

Use `init --profile agent` for larger quotas.
Use `init --profile swarm` for shared knowledge and private worker namespaces.

All profiles use `.instantkv/data` after setup. Setup creates credentials for each configured principal.

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

| Query setting                 | Accepted range                             |
| ----------------------------- | ------------------------------------------ |
| Candidate records examined    | 1–100,000                                  |
| Encoded record bytes examined | 64 KiB–64 MiB                              |
| Complete response cap         | 1 KiB–1 MiB                                |
| Requested result count        | 1–100                                      |
| Requested response budget     | Default 16 KiB; at most the configured cap |

If you lower the response cap below 16 KiB, clients must also lower their request budget.
These limits control scan work and output, not total process RAM.
Logical quotas count the full memory JSON envelope. Index overhead is additional.

Each memory accepts at most 16 KiB content, 8 KiB metadata and eight tags.
Retrieval requires both `get` and `list` grants.
A client with only `list` cannot read values through the memory API.
[Query contract](memory-mvp.md).

## TTL resolution

1. Explicit request TTL, otherwise namespace default.
2. Missing TTL is rejected if `require_ttl = true`; otherwise no expiry.
3. TTL above a configured maximum is rejected, never silently clamped.

A maximum TTL requires `require_ttl = true`. A client cannot bypass it by omitting the TTL.
RAM expiry uses a monotonic clock. Durable expiry uses UTC across restarts.
Expired records are unreadable but count toward quota until cleanup or replacement.

## Credentials and changes

The template uses `INSTANTKV_APP_TOKEN` and `INSTANTKV_READER_TOKEN`.
`init` generates private tokens in `.instantkv/credentials.env`.
Unix file permissions restrict access. Environment values override saved secrets.
The server refuses startup if tokens are missing, duplicated or shorter than 32 bytes.
The reader can get/list knowledge; the app can access all three namespaces.

The swarm operator can access all five namespaces.
Each worker can get/list `shared` and fully access its own knowledge and checkpoints.
These permissions apply to one server. They do not create replicas.
[Swarm setup](cloud-agents.md).

Choose either `namespaces` plus `operations`, or explicit per-namespace `grants`.
Do not combine the two forms.

The shorthand applies the same operations to every listed namespace.
Explicit grants can assign different operations to each namespace:

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

Add a checkpoint grant as shown in the swarm profile.

Checkpoint saves require GET permission for each referenced namespace.
Restore uses current GET grants and marks revoked references as `forbidden`.
The metrics endpoint requires a stats grant in at least one namespace.
It reports aggregate service counters, not a private view for one agent.

Clients select `INSTANTKV_TOKEN`, then `INSTANTKV_APP_TOKEN`, then the saved app token.
`--secrets-file PATH` selects another credentials file.
The CLI does not accept a token argument. MCP uses the same client and authorization.

Configuration and credential changes require a restart.
The server rejects removal of a persisted namespace or changes to its mode or purpose.
Such changes need migration support.
Lower quotas reject writes while usage remains over the limit, including updates that still exceed it.
Explicit deletion can free logical quota. TTL policy changes affect new writes only.
