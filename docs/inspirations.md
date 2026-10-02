# Engineering references

These projects informed repository structure and storage verification.
The table links to their code and documentation. instantKV code and artwork are original.

| Reference                                                                                                                    | What instantKV adopts                                                                                                   |
| ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| [Valkey](https://github.com/valkey-io/valkey)                                                                                | Start the README with something runnable; keep configuration, tests and benchmark commands discoverable                 |
| [TigerBeetle](https://github.com/tigerbeetle/tigerbeetle) and [safety design](https://docs.tigerbeetle.com/concepts/safety/) | Write explicit invariants; verify failed writes preserve state; state durability boundaries and outstanding fault tests |
| [redb](https://github.com/cberner/redb)                                                                                      | Reuse an embedded transactional engine; preserve immediate durability; document its one-writer constraint               |
| [KDE KCoreAddons](https://github.com/KDE/kcoreaddons)                                                                        | Keep source, tests, examples, licensing and CI easy to locate; treat documentation as part of the project               |
| [KDE Extra CMake Modules](https://github.com/KDE/extra-cmake-modules)                                                        | Provide repeatable build checks and clear contributor entry points; use Cargo for this Rust repository                  |
| [MCP Rust SDK](https://github.com/modelcontextprotocol/rust-sdk)                                                             | Use the maintained protocol implementation and typed tool schemas                                                       |

Project checks include locked dependencies, formatting, Clippy, invariant tests and HTTP/MCP tests.
They also include restart demos, container checks, offline restore tests and raw benchmark reports.
Deeper fault tests and real-model evaluation remain on the roadmap.

## Visual direction

The original Monolith artwork uses a chrome split-K, graphite surfaces and Space Grotesk.
It replaced an earlier desktop theme.
The current website uses a black split-K, white surfaces and locally served Geist.
Architecture diagrams retain their original artwork and status labels.
[Editable sources and licenses](assets/README.md).
