# Demo: remember, recall, browse and forget

[Open the browser demo](https://instantkv.com/demo/) to use the current memory API.
Save synthetic memories, clear local context, filter results and delete an exact memory.
Open a separate reader tab to fetch stored values independently.
Recorded mode shows saved responses from fresh memory runs.
[Architecture, bounds and timing](live-demo.md).

## Local memory and a real restart

Build the current source, then run:

```sh
instantkv demo
```

The demo creates private temporary state. It uses the local profile and real HTTP.
It saves structured memory and a checkpoint, clears simulated context and restarts its server.
Then it verifies the exact memory through topic, tag, time and keyword filters.
It browses memory and deletes it with a revision check.

```text
01  REMEMBER  saved content, topic, tag, event time and metadata
02  SAVE      committed checkpoint + latest pointer atomically
03  COMPACT   cleared simulated agent context; locator stays outside it
04  RESTART   reopened the same database with an empty scratch cache
05  RESTORE   recovered goal, constraints, decisions, sources, next action
06  RECALL    topic + tag + time + keywords recovered the exact memory
07  BROWSE    bounded page lists durable memories; scratch is empty
08  FORGET    revision-checked deletion removes the record and indexes
PASS: five memory tools + checkpoint handoff + restart via real HTTP
```

It verifies every saved field, the latest checkpoint pointer and empty scratch.
The script removes its child processes and temporary files.
Context clearing is simulated. It does not measure real-model recall quality.

## Shared facts and private agents

```sh
instantkv demo --swarm
```

The demo saves shared structured memory and separate Alpha/Beta findings.
Workers use separate credentials. Shared facts are readable; sibling access and shared writes fail.
After a real restart, Alpha restores its checkpoint and referenced memories.
Alpha deletes its private finding while shared facts remain available.
The demo creates no replicas and makes no automatic model call.
[Swarm setup](cloud-agents.md).

## Embed without HTTP

```sh
cargo run -p instantkv-core --example memory -- /tmp/instantkv-embedded-demo
```

This example remembers a preference, closes the engine and reopens the same database.
It recalls the preference, browses memory and deletes the record with its revision.
It uses the Rust core directly, without an HTTP server or async runtime.

## Connect a real local model

The [Ollama example](../examples/local-llm.py) reads actual MCP tool schemas.
Run it with your installed model to evaluate tool use and task correctness.
Model evaluation is separate from the storage demos above.
[Memory guide](memory-mvp.md) · [MCP setup](agents.md) · [Current benchmarks](benchmarks.md).

The local CLI demo also calls BM25 `search` after restart and verifies the saved
preference. The browser demo and its archived recordings exercise literal filters.
Use `instantkv search "preferred language for local tooling"` to try ranking.
