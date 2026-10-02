# Agent memory contract

This guide defines checkpoint saves and restores for HTTP and MCP clients.
An agent stores facts as records and task state as a checkpoint.
The API calls the checkpoint's short context note a `capsule`.
The runtime keeps the checkpoint locator outside the prompt so compaction cannot erase it.
The source MVP also supports [structured memory](memory-mvp.md) with topics, tags and event time.

## Memory record

Store small, independently useful JSON values under descriptive keys, for example
`projects/instantkv/decisions/storage-engine`. A suggested value:

```json
{
  "schema_version": 1,
  "kind": "decision",
  "content": "Use redb for the first single-node durable backend.",
  "source": { "type": "file", "locator": "docs/architecture.md" },
  "observed_at": "2026-10-01T08:00:00Z",
  "tags": ["instantkv", "storage"]
}
```

Suggested kinds are `fact`, `decision`, `constraint`, `task` and `reference`.
The server adds a revision, write time and optional expiry.
It validates JSON syntax, not factual accuracy.
Ordinary records accept app-defined fields. Checkpoints use a defined schema.

## Checkpoint → compact → restore

1. Agent writes reusable knowledge as it works.
2. Before compaction, agent creates a checkpoint with `goal`, `summary`,
   `constraints`, `decisions`, `open_tasks`, `next_action`, and optional references.
3. Server validates the entire bundle and atomically commits it with the session's
   latest pointer. It returns checkpoint ID, revision, and stable locator.
4. Runtime keeps `{namespace, agent_id, session_id, checkpoint_id}` in its own
   durable session metadata. Credentials stay in its secret configuration.
5. After compaction, runtime restores that checkpoint, injects the short capsule,
   and lets the agent recall detailed records on demand.

Essential task context stays in the checkpoint bundle.
References contain a namespace, key and expected revision.
Restore reports missing, expired or changed references.
Ordinary keys are mutable; v1 does not retain historical values.
Checkpoint bundles remain immutable until deletion.

Deletion removes retry history. Never reuse a deleted checkpoint ID.

The complete restore response must fit the caller's byte budget.
An insufficient budget returns an error; essential constraints are not silently removed.
Optional details stay in references. The runtime uses its model tokenizer to set token budgets.

| Setting          | Limit or default                               |
| ---------------- | ---------------------------------------------- |
| Capsule          | 16 KiB; at most 64 references                  |
| Complete bundle  | Default cap 1 MiB; configurable downward       |
| Restore response | Default 32 KiB; accepted range 512 bytes–1 MiB |

The local profile has a smaller 64 KiB HTTP body limit.
Byte limits are not model token counts.

## Operations

| HTTP route under `/v1/namespaces/{ns}`                                      | MCP tool                   | Permission |
| --------------------------------------------------------------------------- | -------------------------- | ---------- |
| `PUT /records/{encoded_key}` with raw JSON + optional TTL, conditional ETag | `memory_put`               | put        |
| `GET /records/{encoded_key}`                                                | `memory_get`               | get        |
| `GET /records?prefix=...&limit=...&cursor=...`                              | `memory_list`              | list       |
| `DELETE /records/{encoded_key}`                                             | `memory_delete`            | delete     |
| `POST /checkpoints` with bundle + expected latest revision                  | `memory_checkpoint`        | put        |
| `GET /checkpoints/{id}` or `/sessions/{agent}/{session}/latest`             | `memory_restore`           | get        |
| `DELETE /checkpoints/{id}`                                                  | `memory_delete_checkpoint` | delete     |

Encode a UTF-8 record key as one percent-encoded path segment.
Key limits apply after decoding. Generic routes cannot change reserved checkpoint records.
The current latest checkpoint cannot be deleted until a newer checkpoint exists.

Checkpoint namespaces require durable storage, no TTL and no eviction.
Record lists return metadata: 100 items by default, at most 1,000.
Cursor pages do not form a stable snapshot during writes.

MCP provides model-callable tools with input schemas.
The adapter uses the [official Rust SDK](https://github.com/modelcontextprotocol/rust-sdk) and
[tools specification](https://modelcontextprotocol.io/specification/latest/server/tools).
Not all runtimes provide a pre-compaction hook. Explicit tools and save/restore instructions provide the fallback.

## Success criteria

After compaction and a server restart, the agent must recover the state needed to continue.
That state includes the goal, constraints, decisions, pending work and source references.
Tests must verify capsule content as well as retrieval latency.
Storage tests do not establish real-model task success.
