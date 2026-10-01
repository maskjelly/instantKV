# Demo: store → compact → restore

For the browser demo, [open instantkv.com/demo](https://instantkv.com/demo/).
It writes up to 100,000 synthetic cache records or 10,000 durable records to
the actual Rust service, then recalls exact keys in an independent reader.
[Architecture, limits and timing methodology](live-demo.md).

## Shared knowledge and private cloud agents

```sh
instantkv demo --swarm
# Docker: ./scripts/kv.sh demo --swarm
```

Verified on the local macOS release build and Rove's Linux Docker instance:

```text
01  SHARED    both cloud agents recall the same shared baseline
02  PRIVATE   agents write independently; cross-agent reads and shared writes return 403
03  HANDOFF   saved private capsule; cleared simulated context; locator lives outside it
04  RESTORE   after real server restart, Alpha restores its capsule and both knowledge sources
PASS: shared knowledge + isolated agents + durable handoff over real HTTP
```

The demo creates a fresh swarm profile, seeds shared knowledge as operator, and
uses separate Alpha/Beta credentials for worker calls. It asserts that each agent
can read shared knowledge and write privately, cannot read a sibling's facts or checkpoint,
and cannot overwrite shared knowledge. After context clearing and server kill/restart,
Alpha restores the exact capsule and reads both referenced knowledge sources.
The locator is a separate runtime metadata file. No physical replicas or automatic
consolidation occur. [Deploy this topology](cloud-agents.md).

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

The demo uses an isolated temporary directory, private generated credentials and
real HTTP requests. It checks capsule equality, known knowledge bytes, latest
pointer recovery and missing scratch. It kills and waits for its actual server
child, then starts a new process against the same database. Child processes and
temporary files are cleaned up when it exits.

Compaction is simulated by clearing in-process agent context. The locator is
saved separately in a session metadata file. No LLM call or automatic runtime
hook is implied. The next action above is synthetic task content being recovered.
MCP save/restore is separately verified by the integration test negotiating the
protocol, invoking tools and checking structured results and visible errors.

For actual agents, follow [MCP setup and lifecycle instructions](agents.md).
For measured latency, see [benchmark results](benchmarks.md). For durable recovery
from a backup rather than a restart, use the [restore drill](operations.md).
