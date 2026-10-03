# HTTP reference

This guide describes the Rust node's `/v1` API.
The website's temporary [demo API](live-demo.md) is separate.
For remote access, use TLS at a reverse proxy or an SSH tunnel.

## Authentication and keys

When authentication is enabled, `/v1` requests require `Authorization: Bearer TOKEN`.
Credentials determine the permitted namespace and operation pairs.
`/healthz` is public; `/metrics` requires a stats grant.
Never put tokens in URLs or memory values.

Treat a UTF-8 record key as one percent-encoded path segment: `project/stack`
becomes `project%2Fstack`. Key size limits apply after decoding. Generic keys
beginning `__` are reserved for checkpoint internals.

## Routes

Use `/v1/namespaces/{namespace}` as the base:

| Method and path                          | Request / response                                                                                        |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `POST /memories`                         | Structured memory; create-only or revision-protected update; returns memory, key, revision and timestamps |
| `GET /memories`                          | Topic/tag/query/since_ms/until_ms/limit/max_bytes/cursor; bounded values; requires get + list             |
| `POST /search`                           | JSON query and optional filters; BM25 scores, next_cursor and work counters; requires get + list |
| `GET /memories/{key}`                    | Exact structured memory with revision and timestamps                                                      |
| `DELETE /memories/{key}`                 | Deletes structured memory and indexes; optional If-Match; 204                                             |
| `PUT /records/{key}`                     | Raw value bytes; optional `ttl_seconds` query; returns revision, bytes, write/expiry timestamps           |
| `GET /records/{key}`                     | Original bytes, namespace content type and quoted revision `ETag`                                         |
| `DELETE /records/{key}`                  | Deletes an ordinary key; 204 on success                                                                   |
| `GET /records`                           | `prefix`, `limit`, `cursor` query; bounded metadata page                                                  |
| `GET /stats`                             | Logical namespace entries, bytes and revision counters                                                    |
| `POST /checkpoints`                      | Typed checkpoint request; returns receipt with stable locator and latest revision                         |
| `GET /checkpoints/{id}`                  | Bounded restore response; `max_bytes` query                                                               |
| `GET /sessions/{agent}/{session}/latest` | Restore the session's latest checkpoint; `max_bytes` query                                                |
| `DELETE /checkpoints/{id}`               | Prunes an old bundle; 204; refuses deletion of current latest                                             |

Record reads choose `application/json`, `text/plain; charset=utf-8` or
`application/octet-stream` from the namespace admission kind. Metadata/checkpoint
responses are JSON. The node sends `Cache-Control: no-store`.

Memory routes belong to the unreleased source MVP.
`POST /memories` uses a nested `memory` object. MCP accepts those fields directly.
[Memory guide](memory-mvp.md#http-and-mcp) · [Schemas](../examples/memory.schema.json).

Ranked requests also accept `expand` (default false) and `expansion_terms`
(default empty). Responses report `query_reduced`, `selected_terms`, `index_reads`,
`scored_candidates`, `expansion_terms` and `truncated`. See the memory guide for
limits and the ranked cursor upgrade rule.

The original KV and checkpoint routes remain compatible. Time filters use inclusive Unix milliseconds.
Continue with the same cursor filters, including after empty pages.

## First record over HTTP

After local setup, load only your generated private credentials file.
Disable shell tracing before loading credentials.

The example sends the token through stdin, not a process argument:

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

Supply each worker's scoped token through its secret environment.
Target the worker's private namespace.

The complete server credentials file belongs to the operator. MCP and CLI handle bearer authentication for you.

## Conditional writes and TTL

For conditional raw KV writes, use one of these headers:

- `If-None-Match: *`: create only if the key is absent.
- `If-Match: "REVISION"`: update or delete only the observed revision.

Without either header, raw KV writes and deletes are unconditional.
Conflicts return 409. Revision conditions do not retrieve historical values.
Structured memory instead uses `if_revision` in its POST body and `If-Match` on DELETE.

`?ttl_seconds=60` sets the TTL for a raw KV write.
Namespace default, required and maximum TTL rules still apply. Above-limit requests fail.
Checkpoint namespaces require durable storage, no TTL and no eviction.
[Configuration](configuration.md).

## Checkpoint and restore

POST the [checkpoint example](../examples/checkpoint.json) with `Content-Type: application/json`.
Use a unique ID for each new checkpoint.
Set `expected_latest_revision` to the previous receipt's `latest_revision`.

Restore defaults to 32 KiB. It accepts budgets from 512 bytes to 1 MiB.
An insufficient budget returns an error instead of removing essential fields.
References report current status and revision without including every value.
Save requires GET permission on referenced namespaces.
Restore reports `forbidden` if current grants deny those references.
[Checkpoint contract](agent-memory.md).

## Errors and retries

| Status    | Meaning / next action                                                       |
| --------- | --------------------------------------------------------------------------- |
| 400       | Invalid request, policy violation or budget; inspect the body and fix input |
| 401 / 403 | Missing/invalid credential or insufficient grants                           |
| 404       | Missing namespace, record or checkpoint; expired records are unavailable    |
| 409       | Revision/payload conflict or protected latest checkpoint                    |
| 413       | Request body exceeds configured limit                                       |
| 507       | Logical namespace quota exceeded; delete deliberately or adjust policy      |
| 503       | Storage unavailable or admission full; inspect logs or back off             |
| 504       | Response deadline; a submitted write may still commit                       |

Application errors contain `error.code`, `error.message` and `error.retryable`.
Framework body/query errors can use another response shape.

After a timeout, inspect the revision or retry the same checkpoint ID with the same payload.
Do not retry by overwriting with a new ID.

The timeout limits the response wait. It does not cancel a transaction that has already started.
