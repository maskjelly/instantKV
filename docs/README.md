# Documentation map

Start with one path. Reference pages explain contracts; evidence pages explain measurements.

## Run local memory

1. [Quick start](quickstart.md): build the source MVP and save your first memory.
2. [Connect through MCP](agents.md): give your agent the memory tools.
3. [Memory guide](memory-mvp.md): filters, ranking, pagination and limits.

For task continuation, read the [checkpoint contract](agent-memory.md).
For in-process use, run the [Rust example](../crates/instantkv-core/examples/memory.rs).

## Reference and operations

- [CLI](cli.md) and [HTTP](http.md): commands and routes.
- [Configuration](configuration.md): quotas, credentials and namespace grants.
- [Operations](operations.md): backup, restore and upgrade procedures.
- [Local-device status](local-first.md): supported builds and untested devices.
- [Shared/private namespaces](cloud-agents.md): optional multi-agent setup.

## Evidence

- [Performance](performance.md): measured results and unverified targets.
- [Full retrieval report](benchmarks/2026-10-04-full-retrieval/README.md): scores, raw outputs and comparison limits.
- [Benchmark methodology](benchmarks.md) and [evaluation policy](evaluation-policy.md).
- [Historical records](history/README.md) and raw reports in `benchmarks/` and `demo-results/` are separate from current instructions.

## Maintain the project

- [Contributor guide](../CONTRIBUTING.md), [repository maintenance](repository.md) and [architecture](architecture.md).
- [Cleanup and release plan](project-plan.md): ordered work and acceptance gates.
- [Roadmap](roadmap.md): current scope and deferred work.
- [Validation record](validation/2026-10-06.md): checks and local experiments for this cleanup.
- [Website](website.md): site structure, design decisions and publication checks.
- [Private installation reporting](install-metrics.md): local download snapshots and counting limits.

The [distributed proposal](proposals/distributed-memory.md) is future design work.
