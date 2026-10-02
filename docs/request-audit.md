# Product and request audit

Updated: 2026-10-03. This page records current behavior and links to its evidence.
[Verification history](checkpoints.md) retains earlier stages and design changes.

## Current source and deployment

The structured-memory MVP is implemented in source and remains unreleased.
The earlier 0.1.2 archives do not contain its new memory tools.

The refreshed runtime source is
[`db26d1a`](https://github.com/maskjelly/instantKV/commit/db26d1a08a1f802dad13ac11c7340222d15950e0).
It passed [Linux x86_64, Linux ARM64, macOS ARM64 and container CI](https://github.com/maskjelly/instantKV/actions/runs/37060413210)
and [website CI](https://github.com/maskjelly/instantKV/actions/runs/37060413178).
Fresh benchmark and demo reports identify the exact runtime source and binary hash.
The recorder also hashes its own code, fixtures, gateway and config.
The verified Linux binary is deployed to the single-agent, swarm and demo services.
Existing values and checkpoint restores match their pre-upgrade hashes.
The deployed CLI demos, filtered retrieval, real restarts and revision-checked deletion passed.

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
Production browser verification repeated the 72 layout checks and all interactions
on `instantkv.com`, with zero browser errors. It saved 100 memories on desktop
and 1,000 on mobile; these smoke runs are separate from the measured workloads.
Published raw reports and agent docs matched the source files byte for byte.

Storage tests verify persistence and transport. CLI demos simulate context clearing.
Real-model recall quality, native phone support, battery use and deeper disk-failure tests remain pending.
Linux ARM64 CI does not establish performance on a physical ARM board.
