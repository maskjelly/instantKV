# Product and request audit

Updated: 2026-10-03. This page records current behavior and links to its evidence.
[Verification history](checkpoints.md) retains earlier stages and design changes.

## Current source and deployment

The structured-memory MVP is implemented in source and remains unreleased.
The earlier 0.1.2 archives do not contain its new memory tools.

Commit [`d6f08d7`](https://github.com/maskjelly/instantKV/commit/d6f08d7b895963f228c2eb3d68a14a94d045d34d)
passed [Linux x86_64, Linux ARM64, macOS ARM64 and container CI](https://github.com/maskjelly/instantKV/actions/runs/37053181372).
Its [website CI](https://github.com/maskjelly/instantKV/actions/runs/37053181391) also passed.
The Rust build was deployed to the existing single-agent, swarm and public-demo instances.
Existing values and checkpoints matched their pre-upgrade checks.

## Requested work

| Request                          | Current result                                                          | Evidence                                                                                 |
| -------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Local memory for LLMs            | Four tools; content, topic, tags, event time and metadata               | [Memory guide](memory-mvp.md)                                                            |
| Small, configurable service      | One Rust binary; local limits; embedded core                            | [Local profile](../config/local.toml), [device support](local-first.md)                  |
| Simple retrieval                 | Ordered topic/tag/time indexes; bounded literal keywords                | [Query contract](memory-mvp.md#keyword-retrieval-and-pagination)                         |
| Recovery after compaction        | Immutable checkpoint and latest pointer in one transaction              | [Checkpoint contract](agent-memory.md)                                                   |
| Shared facts and private workers | One server with per-namespace grants                                    | [Swarm guide](cloud-agents.md)                                                           |
| Real memory benchmarks           | Three 10,000-memory Mac runs; all 30,000 recovered                      | [Performance](performance.md), [raw report](benchmarks/2026-10-03-memory/mac-arm64.json) |
| Clear device targets             | Defined ARM-board workload; targets labeled unverified                  | [Device targets](performance.md#next-device-targets--not-yet-measured)                   |
| Clean website                    | White surfaces, neutral type, local Geist and expandable diagrams       | [Website guide](website.md)                                                              |
| Working public demo              | Current memory tools, filtered queries, paging and deletion                       | [Demo architecture](live-demo.md)                                                        |
| Agent-readable documentation     | Typed MCP tools, schemas, `llms.txt` and `llms-full.txt`                | [MCP setup](agents.md), [website guide](website.md)                                      |
| Simple integration               | Rust embedding and an optional Ollama tool loop                         | [Memory integration](memory-mvp.md#connect-an-actual-local-model)                        |
| Future direction                 | Local-model tests, native phones, exports and optional richer retrieval | [Roadmap](roadmap.md)                                                                    |
| Distributed memory planning      | Historical snapshots, private branches and reviewed shared updates      | [Proposal](distributed-memory.md)                                                        |
| Clear, brief writing             | ASD-STE100 principles with natural software terms                       | [Contributor guidance](../CONTRIBUTING.md#writing-style)                                 |

## Verification limits

The current changes passed 42 Rust tests, three Python contract tests and nine website/demo tests.
Local browser verification passed 72 layout checks at four viewport widths.
It also verified current memory saves, combined topic/tag/time filters, cursor continuation,
independent readers, revision-checked deletion, empty index results after deletion,
mobile pause/resume and saved queries with zero recorded-mode storage requests.
The single-agent, swarm and embedded Rust demos passed with real storage.

Storage tests verify persistence and transport. CLI demos simulate context clearing.
Real-model recall quality, native phone support, battery use and deeper disk-failure tests remain pending.
Linux ARM64 CI does not establish performance on a physical ARM board.
