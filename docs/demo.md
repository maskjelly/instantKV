# Demo: store → compact → restore

[Open the browser demo](https://instantkv.com/demo/).
Recorded mode replays Mac measurements. Live VPS mode writes temporary records to the Rust service.
It supports up to 100,000 cache records or 10,000 durable records.
The separate reader retrieves exact keys.
[Architecture, limits and timing](live-demo.md).

## Shared knowledge and private local agents

```sh
instantkv demo --swarm
# Docker: ./scripts/kv.sh demo --swarm
```

Verified on the local macOS release build and Rove's Linux Docker instance:

```text
01  SHARED    both agents recall the same shared baseline
02  PRIVATE   agents write independently; cross-agent reads and shared writes return 403
03  HANDOFF   saved private capsule; cleared simulated context; locator lives outside it
04  RESTORE   after real server restart, Alpha restores its capsule and both knowledge sources
PASS: shared knowledge + isolated agents + durable handoff over real HTTP
```

The CLI swarm demo creates a fresh profile and seeds shared facts as operator.
Worker calls use separate Alpha/Beta credentials.
Tests verify shared reads, private writes and forbidden sibling access.
They also reject shared writes and out-of-scope checkpoint references.
After context clearing and a real server restart, Alpha restores its capsule and referenced facts.
The locator remains in a separate runtime metadata file.

The demo creates no replicas and performs no automatic consolidation.
[Swarm setup](cloud-agents.md).

## Single-agent knowledge and scratch

```sh
instantkv demo
# Docker: ./scripts/kv.sh demo
```

Verified locally and on Rove's Linux Docker deployment on 2026-10-01:

```text
01  STORE     saved project/storage in durable knowledge
02  SAVE      committed checkpoint + latest pointer atomically
03  COMPACT   cleared simulated agent context; locator stays outside it
04  RESTART   reopened the same database with an empty scratch cache
05  RESTORE   recovered goal, constraints, decisions, sources, next action
06  RECALL    durable knowledge survived; disposable scratch did not

Next action: Implement memory_get and memory_checkpoint tools
PASS: compaction handoff and database restart via real HTTP requests
```

The demo uses a temporary directory, generated private credentials and real HTTP.
It verifies capsule equality, known record bytes, latest-pointer recovery and empty scratch.
It terminates its server process, then starts a new process with the same database.
It removes its child processes and temporary files afterward.

Compaction is simulated by clearing the agent's in-process context.
The locator stays in a separate session metadata file.
The demo makes no LLM call and uses no automatic runtime hook.
The recovered next action above is synthetic task content.
Separate MCP tests negotiate the protocol and verify tool results and visible errors.

[MCP setup](agents.md) explains real-agent integration.
[Benchmarks](benchmarks.md) records latency measurements.
The [restore test](operations.md) verifies recovery from an offline backup.
