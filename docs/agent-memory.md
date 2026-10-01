# Agent memory contract

This is the save/restore contract for HTTP and MCP clients. An agent saves facts
as records and its continuation state as a checkpoint. The runtime keeps the
checkpoint ID outside the prompt so it can load that state after compaction.
The checkpoint's short context note is called a `capsule` in the API.

## Memory record

Store small, independently useful JSON values under descriptive keys, for example
`projects/instantkv/decisions/storage-engine`. A suggested value:

```json
{
  "schema_version": 1,
  "kind": "decision",
  "content": "Use redb for the first single-node durable backend.",
  "source": {"type": "file", "locator": "docs/architecture.md"},
  "observed_at": "2026-10-01T08:00:00Z",
  "tags": ["instantkv", "storage"]
}
```

Suggested kinds: `fact`, `decision`, `constraint`, `task`, `reference`. The server
adds a revision, write time and optional expiry. It checks JSON syntax, not whether
the content is true. You choose the fields in ordinary records; checkpoints have
a defined schema that the server validates.

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

Essential restore context lives inside the bundle. References include namespace,
key, and expected revision; missing, expired, or changed references are reported.
Normal keys are mutable and revisions detect change; v1 does not promise historical
versions. Checkpoint bundles are immutable until explicitly deleted. Deleting old bundles
removes their retry history; generate unique IDs and never reuse deleted IDs.

The entire serialized restore response must fit the caller's byte budget. Reject an undersized restore
budget explicitly; never silently drop essential constraints. Optional details
are returned as references. Token budgeting belongs to the runtime/model tokenizer.
Capsules are limited to 16 KiB and 64 references. The default total bundle cap is
1 MiB, configurable downward. Restore defaults to 32 KiB; accepted budgets are
512 bytes through 1 MiB. Byte limits are not model token counts.

## Operations

| HTTP route under `/v1/namespaces/{ns}` | MCP tool | Permission |
|---|---|---|
| `PUT /records/{encoded_key}` with raw JSON + optional TTL, conditional ETag | `memory_put` | put |
| `GET /records/{encoded_key}` | `memory_get` | get |
| `GET /records?prefix=...&limit=...&cursor=...` | `memory_list` | list |
| `DELETE /records/{encoded_key}` | `memory_delete` | delete |
| `POST /checkpoints` with bundle + expected latest revision | `memory_checkpoint` | put |
| `GET /checkpoints/{id}` or `/sessions/{agent}/{session}/latest` | `memory_restore` | get |
| `DELETE /checkpoints/{id}` | `memory_delete_checkpoint` | delete |

UTF-8 record keys are one percent-encoded path segment, bounded after decoding.
Reserved checkpoint keys cannot be mutated through generic record routes. Deleting
the current latest checkpoint is rejected until a newer checkpoint is saved.
Checkpoint namespaces must be durable with no TTL and no eviction; arbitrary TTL
records remain separate. Listing defaults to 100 items with a server cap of 1000
with key/value admission bounds; cursors do not promise a stable snapshot during writes.

MCP exposes model-callable tools with input schemas; see the
[official tools specification](https://modelcontextprotocol.io/specification/latest/server/tools).
The adapter uses the [official Rust SDK](https://github.com/modelcontextprotocol/rust-sdk). Integration cannot
assume every agent runtime exposes a pre-compaction hook: offer explicit tools and
a documented save/restore instruction as the fallback.

## Success criteria

After compaction **and a server restart**, an agent can recover its goal,
constraints, completed decisions, pending work, and source references without
re-reading the entire conversation. Test the capsule content as well as retrieval
latency. Storing text alone does not verify successful continuation.
