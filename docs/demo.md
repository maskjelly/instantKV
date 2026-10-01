# Demo: park → compact → restore

```sh
instantkv demo
# Docker: ./scripts/kv.sh demo
```

Verified locally and on Rove's Linux Docker deployment on 2026-10-01:

```text
01  PARK      saved project/storage in durable knowledge
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
