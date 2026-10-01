# Why instantKV

Your agent has already worked out the stack, found the bug and chosen the next
step. Save that work somewhere it can come back to after compaction or a restart.
That's what instantKV is for.

Put a fact under a key. Save a checkpoint before clearing context. Load it when
the agent returns. You choose what to keep; instantKV stores it and returns the
record you ask for, without a model call.

## Who should use it

Coding agents with long tasks. Remote workers that restart. Swarms that need the
same project facts and separate private notes. Developers who already have an
agent runtime and want to add a small memory service to it.

Run the native binary or Docker container on a machine you control. Connect
through HTTP, the CLI or MCP. A checkpoint holds the goal and next action;
larger details stay in records until the agent needs them.

## What makes it worth using

- **One process to run.** The database lives inside the Rust service. No separate
  vector or graph database is needed.
- **Exact recall.** Read the saved record by key. Use revisions to spot changes
  and avoid overwriting someone else's update.
- **Checkpoints built in.** The context note and the session's latest checkpoint
  commit together. A restore reports changed, missing or inaccessible references.
- **Shared facts, private work.** Give workers read-only project knowledge and
  separate namespaces (storage sections with their own permissions) for notes.
  Permissions apply to every request.
- **No model calls for memory.** Storing and reading records require no LLM or embedding
  calls. The self-hosted software has no per-agent or per-request fee; you still
  pay for infrastructure and upkeep.

That combination is the pitch: a small service you can run beside your agents,
with the save/restore plumbing already written.

## How the alternatives compare

Reviewed against official documentation on 2026-10-01. The last column is our
judgment about fit, not a result from testing those products.

| Tool | What it gives you | When to choose it |
|---|---|---|
| [Mem0](https://docs.mem0.ai/open-source/overview) | A memory layer with configurable models, embeddings and vector storage; its [default flow](https://docs.mem0.ai/open-source/python-quickstart) extracts facts and searches memories | You want it to choose facts from conversations and find related memories by meaning |
| [Zep / Graphiti](https://help.getzep.com/graphiti/getting-started/welcome) | Memory built around changing facts and relationships; Graphiti's [setup](https://help.getzep.com/graphiti/getting-started/quick-start) uses a graph backend and model providers | Relationships and time matter to retrieval, and you want graph-based search |
| [Letta](https://docs.letta.com/agent-sdk) | A stateful agent SDK with [persistent memory](https://docs.letta.com/agent-sdk/memory), git-backed files and background memory updates | You want the agent runtime and memory system together |
| [Upstash Redis](https://upstash.com/redis) | Managed Redis over HTTP or TCP, durable storage and multi-region replication | You want someone else to operate the database, or your application needs Redis features |
| [Valkey](https://valkey.io/topics/transactions/) | A general-purpose key/value server with transactions, [persistence](https://valkey.io/topics/persistence/) and [clustering](https://valkey.io/topics/cluster-tutorial/) | You need its broader database features and want to build the agent handoff logic yourself |
| instantKV | Exact records, durable checkpoints, shared/private permissions, HTTP/CLI/MCP in one self-hosted Rust service | You know what the agent should save and want a direct way to store it and resume work |

Several alternatives can be self-hosted. Mem0's components can use local models,
and its behavior depends on configuration. Self-hosting and exact retrieval are
not exclusive to instantKV. instantKV packages the handoff tools with the storage:
keep your runtime, run one memory service, and use its existing checkpoint tools.

## The evidence so far

The [recorded HTTP benchmark](benchmarks.md) measured a median **4,010 knowledge
reads/second** across three runs on a busy shared VPS. The observed container
memory after the runs was **10.3 MiB**, a snapshot rather than peak usage.

The public demo wrote **100,000 cache records / 68.25 MiB** and **10,000 durable
records / 6.82 MiB**, with zero failed API requests in both runs. Exact reads and
independent-tab recall passed. [Reports and timing definitions](live-demo.md#recorded-live-verification).

We haven't run a shared workload against these competitors, so those results
don't establish a speed or total-cost ranking. instantKV is an early single-node
release. Semantic search, automatic runtime hooks, distributed replicas and
automatic consolidation are [planned](roadmap.md).

Try the [browser demo](https://instantkv.com/demo/) or
[run your own node](quickstart.md). Here, memory means agent knowledge and saved
task context; a model's inference KV cache stays in its model runtime.
