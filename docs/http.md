# HTTP reference

Send requests to your own Rust node. This guide describes its `/v1` API; the
public website's temporary [demo API](live-demo.md) is separate. For remote
access, configure TLS at a reverse proxy or use an SSH tunnel.

## Authentication and keys

All `/v1` operations require `Authorization: Bearer TOKEN` when auth is enabled.
Credentials determine allowed namespace/operation pairs. `/healthz` is public;
`/metrics` requires a stats grant. Never put tokens in URLs or memory values.

Treat a UTF-8 record key as one percent-encoded path segment: `project/stack`
becomes `project%2Fstack`. Key size limits apply after decoding. Generic keys
beginning `__` are reserved for checkpoint internals.

## Routes

Use `/v1/namespaces/{namespace}` as the base:

| Method and path | Request / response |
|---|---|
| `PUT /records/{key}` | Raw value bytes; optional `ttl_seconds` query; returns revision, bytes, write/expiry timestamps |
| `GET /records/{key}` | Original bytes, namespace content type and quoted revision `ETag` |
| `DELETE /records/{key}` | Deletes an ordinary key; 204 on success |
| `GET /records` | `prefix`, `limit`, `cursor` query; bounded metadata page |
| `GET /stats` | Logical namespace entries, bytes and revision counters |
| `POST /checkpoints` | Typed checkpoint request; returns receipt with stable locator and latest revision |
| `GET /checkpoints/{id}` | Bounded restore response; `max_bytes` query |
| `GET /sessions/{agent}/{session}/latest` | Restore the session's latest checkpoint; `max_bytes` query |
| `DELETE /checkpoints/{id}` | Prunes an old bundle; 204; refuses deletion of current latest |

Record reads choose `application/json`, `text/plain; charset=utf-8` or
`application/octet-stream` from the namespace admission kind. Metadata/checkpoint
responses are JSON. The node sends `Cache-Control: no-store`.

## First record over HTTP

On your own machine, after the default binary setup, load only your locally
generated private credentials file. Avoid shell tracing when handling secrets.
The config below feeds the token through stdin rather than a process argument.

```sh
set +x
. .instantkv/credentials.env
printf 'header = "Authorization: Bearer %s"\n' "$INSTANTKV_APP_TOKEN" |
  curl --config - --fail-with-body --request PUT \
    --header 'Content-Type: application/json' \
    --header 'If-None-Match: *' \
    --data '{"content":"Rust + redb"}' \
    'http://127.0.0.1:8080/v1/namespaces/knowledge/records/project%2Fstack'
printf 'header = "Authorization: Bearer %s"\n' "$INSTANTKV_APP_TOKEN" |
  curl --config - --fail-with-body --include \
    'http://127.0.0.1:8080/v1/namespaces/knowledge/records/project%2Fstack'
```

For cloud workers inject their scoped token securely and target their private
namespace. The server credentials file is operator-only. MCP and CLI perform
this authentication for you.

## Conditional writes and TTL

Use exactly one of `If-None-Match: *` for create-if-absent or
`If-Match: "REVISION"` for an observed revision on PUT/DELETE. Without either,
the operation is unconditional. The server returns 409 on conflicts. Revision
conditions are not historical-value retrieval.

`?ttl_seconds=60` sets a per-write TTL, subject to the namespace's required/default
and maximum TTL policy. Above-limit requests fail rather than clamp. Checkpoints
require durable namespaces with no TTL or eviction. See [configuration](configuration.md).

## Checkpoint and restore

POST [the complete example](../examples/checkpoint.json) to the checkpoint route
with `Content-Type: application/json`. Use a unique ID for each new handoff and
the last receipt's `latest_revision` as `expected_latest_revision`.

Restore defaults to 32 KiB; permitted budgets are 512 bytes to 1 MiB. An undersized
budget fails rather than dropping essential capsule fields. References report
their current status and revision without embedding every record. Save requires
GET permission on referenced namespaces; restore reports `forbidden` if current
grants no longer allow those references. See [the memory contract](agent-memory.md).

## Errors and retries

| Status | Meaning / next action |
|---|---|
| 400 | Invalid request, policy violation or budget; inspect the body and fix input |
| 401 / 403 | Missing/invalid credential or insufficient grants |
| 404 | Missing namespace, record or checkpoint; expired records are unavailable |
| 409 | Revision/payload conflict or protected latest checkpoint |
| 413 | Request body exceeds configured limit |
| 507 | Logical namespace quota exceeded; delete deliberately or adjust policy |
| 503 | Storage unavailable or admission full; inspect logs or back off |
| 504 | Response deadline; a submitted write may still commit |

Application errors have `error.code`, `error.message` and `error.retryable`.
Framework-level body/query rejection responses may use a different shape.
After an ambiguous timeout inspect the revision, or retry the exact immutable
checkpoint ID with the exact same payload. Do not blindly overwrite with a new ID.
The request timeout bounds the response wait, not a transaction already running.
