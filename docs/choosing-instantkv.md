# Why instantKV

instantKV stores facts and task state outside the model's context window.
After a context reset or restart, your agent can retrieve that state and continue.

Four tools save, find, list and delete structured memories.
Checkpoints preserve the goal and next action before compaction.
Your runtime selects what to keep. Storage and retrieval need no model call.

## Who should use it

The service fits local LLM apps, coding agents and tasks that continue across sessions.
Multiple workers can share project facts while keeping private notes.
Developers can add it to an existing runtime through HTTP, CLI, MCP or the Rust core.

The native binary runs beside your model. Docker is optional.
Checkpoints contain the essential task state; detailed facts remain in separate records.

## What makes it worth using

- **One process to run.** The database lives inside the Rust service. No separate
  vector or graph database is needed.
- **Exact recall.** Read the saved record by key. Use revisions to spot changes
  and avoid overwriting someone else's update.
- **Simple discovery.** The source MVP adds indexed topic/tag/time retrieval and
  bounded content keywords, with custom metadata. No embeddings are required.
- **Checkpoints built in.** The context note and the session's latest checkpoint
  commit together. A restore reports changed, missing or inaccessible references.
- **Shared facts, private work.** Give workers read-only project knowledge and
  separate namespaces (storage sections with their own permissions) for notes.
  Permissions apply to every request.
- **No model calls for memory.** Storing and reading records require no LLM or embedding
  calls. The local-first software has no per-agent or per-request fee; you still
  use your own hardware and handle backups.

The storage, permissions and checkpoint tools work together in one local process.
The host runtime still controls memory selection and model context.

## How the alternatives compare

Reviewed against official documentation on 2026-10-01. The last column is our
judgment about fit, not a result from testing those products.

| Tool                                                                       | What it gives you                                                                                                                                                                   | When to choose it                                                                         |
| -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| [Mem0](https://docs.mem0.ai/open-source/overview)                          | A memory layer with configurable models, embeddings and vector storage; its [default flow](https://docs.mem0.ai/open-source/python-quickstart) extracts facts and searches memories | You want it to choose facts from conversations and find related memories by meaning       |
| [Zep / Graphiti](https://help.getzep.com/graphiti/getting-started/welcome) | Memory built around changing facts and relationships; Graphiti's [setup](https://help.getzep.com/graphiti/getting-started/quick-start) uses a graph backend and model providers     | Relationships and time matter to retrieval, and you want graph-based search               |
| [Letta](https://docs.letta.com/agent-sdk)                                  | A stateful agent SDK with [persistent memory](https://docs.letta.com/agent-sdk/memory), git-backed files and background memory updates                                              | You want the agent runtime and memory system together                                     |
| [Upstash Redis](https://upstash.com/redis)                                 | Managed Redis over HTTP or TCP, durable storage and multi-region replication                                                                                                        | You want someone else to operate the database, or your application needs Redis features   |
| [Valkey](https://valkey.io/topics/transactions/)                           | A general-purpose key/value server with transactions, [persistence](https://valkey.io/topics/persistence/) and [clustering](https://valkey.io/topics/cluster-tutorial/)             | You need its broader database features and want to build the agent handoff logic yourself |
| instantKV                                                                  | BM25 document ranking, exact records, durable checkpoints, shared/private permissions, HTTP/CLI/MCP in one local-first Rust process                                                                        | You know what the agent should save and want a direct way to store it and resume work     |

Several alternatives support self-hosting. Mem0 can use local models, depending on its configuration.
instantKV combines direct record access with checkpoint tools; it does not replace your agent runtime.

## The evidence so far

The source MVP's [structured-memory benchmark](performance.md) used three fresh 10,000-memory databases on an M4 Pro.
Topic query p95 was **0.152–0.173 ms**. The largest sampled server RSS was **20.88 MiB**.
All **30,000** memories were verified after abrupt restarts.
These warm local-HTTP results exclude the model and phones.

The [full retrieval report](benchmarks/2026-10-04-full-retrieval/README.md) uses
all 500 LongMemEval-S questions and all ten LoCoMo histories. Model QA scoring is pending.

These alternatives have not been compared in this suite. Supermemory local is
measured separately in the [retrieval notes](memory-benchmark-notes.md).
The results do not establish a speed or cost ranking.
Semantic search, automatic runtime hooks and replicas remain [planned](roadmap.md).

[Run your own node](quickstart.md) and read the [benchmark limits](performance.md).
Agent knowledge and task checkpoints are separate from a model's inference KV cache.

A separate [SciFact comparison](benchmarks/2026-10-04-search/README.md) measured
instantKV BM25 against the recorded Supermemory local control: 81.43% versus 74.80% Recall@10.
Full ArguAna scored 76.96% versus 56.40%, with zero query rejections.
688 searches hit work limits; 1,149 used reduced queries. Supermemory was not rerun here.
That result applies to the tested corpus and configurations. It does not rank
the other products above or measure real-agent memory quality.
