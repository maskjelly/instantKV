# Engineering references

These projects helped us decide how to organize the repo and check the storage
engine. The table links to their code and docs, with the practices we adopted.
instantKV's code and artwork are original.

| Reference | What instantKV adopts |
|---|---|
| [Valkey](https://github.com/valkey-io/valkey) | Start the README with something runnable; keep configuration, tests and benchmark commands discoverable |
| [TigerBeetle](https://github.com/tigerbeetle/tigerbeetle) and [safety design](https://docs.tigerbeetle.com/concepts/safety/) | Write explicit invariants; verify failed writes preserve state; state durability boundaries and outstanding fault tests |
| [redb](https://github.com/cberner/redb) | Reuse an embedded transactional engine; preserve immediate durability; document its one-writer constraint |
| [KDE KCoreAddons](https://github.com/KDE/kcoreaddons) | Keep source, tests, examples, licensing and CI easy to locate; treat documentation as part of the project |
| [KDE Extra CMake Modules](https://github.com/KDE/extra-cmake-modules) | Provide repeatable build checks and clear contributor entry points; use Cargo for this Rust repository |
| [MCP Rust SDK](https://github.com/modelcontextprotocol/rust-sdk) | Use the maintained protocol implementation and typed tool schemas |

Concrete checks here: locked dependencies, formatting, strict Clippy, invariant
and HTTP/MCP tests, a restart demo, non-root container, offline backup drill, and
workload-specific benchmarks with raw results. The roadmap separately records
fault-injection and actual runtime integration still needed.

## Visual direction

Monolith is the original identity: three chrome planes form a split K, paired
with graphite surfaces, silver text, fine borders and Space Grotesk typography.
This replaced the earlier desktop theme. The
architecture, swarm topology, compaction handoff and future consolidation proposal
share this visual language and explicitly label what is implemented.
Editable shapes/text and licensed embedded type live in [assets](assets/README.md).
