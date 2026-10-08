# Technology and learning map

Start with the request path:

`OpenCode → MCP controller → local HTTP → Rust policy → redb transaction`

OpenCode supplies the model and chooses tool calls. The optional Python controller
handles fact identity, provenance, corrections, conflicts and forgetting. Rust
handles authorization, bounded retrieval and durable storage. The website is a
separate static documentation deployment.

## Learn these first

| Order | Topic | What to understand | Read the implementation |
| --- | --- | --- | --- |
| 1 | Transactions and indexes | A fact, its search postings, counters and indexes must change together. A failed write must preserve the old state. | [Store](../crates/instantkv-core/src/store.rs), [architecture](architecture.md) |
| 2 | Memory lifecycle | Identity, observations, current truth, historical evidence, contradictions and explicit corrections are different things. | [Controller](../examples/memory_controller/lifecycle.py), [design](memory-controller-design.md) |
| 3 | Revision checks and retries | Compare-and-swap prevents lost updates. Per-slot receipts make identical retries safe. A timeout can follow a committed write. | [Controller guide](memory-controller.md), [HTTP contract](http.md) |
| 4 | Retrieval | Inverted indexes, BM25 scoring, stemming, WAND skipping, filters, cursors and bounded work determine what reaches the model. | [Search](../crates/instantkv-core/src/search.rs), [memory guide](memory-mvp.md) |
| 5 | Agent integration | MCP exposes tools; the agent chooses when to call them. Prompts and tool schemas affect capture and recall quality. | [MCP setup](agents.md), [OpenCode setup](opencode-memory-demo.md) |
| 6 | Operating a product | Private credentials, namespace grants, backups, upgrades, failure messages and finite capacity matter during daily use. | [Operations](operations.md), [configuration](configuration.md) |

## Rust service

| Technology | Job in this project | Study more deeply |
| --- | --- | --- |
| Rust 2024, Rust 1.98+, Cargo | Two workspace crates: embedded core and service/CLI. Ownership, borrowing and types constrain state and resource use. | Ownership, lifetimes, error enums, shared state, workspace builds |
| redb | Embedded durable database. Record, index and checkpoint changes use transactions. One process owns the database. | ACID, read/write transactions, crash recovery, ordered composite keys |
| Ordered indexes | Topic, tag, event-time and expiry selection without scanning every record. | Key ordering, range scans, index consistency, cursor continuation |
| BM25 and WAND | Rank lexical matches using an inverted index; skip candidates with score bounds. | Term frequency, document frequency, length normalization, safe score bounds |
| `rust-stemmers` | English Snowball stemming during indexing and querying. | Tokenization, morphology and language-specific retrieval limits |
| Tokio | Async network I/O, process management, shutdown and concurrency control. Storage work uses blocking tasks. | Futures, cancellation, semaphores, backpressure, `spawn_blocking` |
| Axum | HTTP routes, request extraction and middleware. | Body limits, authentication, deadlines, structured errors |
| reqwest + rustls | Rust HTTP client and TLS implementation. | Timeouts, transport errors, safe retries |
| Serde, serde_json, TOML | Typed records, JSON wire formats and configuration. | Schema evolution, strict validation, serialization |
| Schemars | JSON Schema generation from Rust API types. | Keeping code, generated schemas and tools consistent |
| clap | Typed command-line arguments and help. | Usable defaults, validation and error paths |
| rmcp | Native Rust MCP tools over stdio, with local or HTTP-backed access. | JSON-RPC, initialization, tool schemas, permission boundaries |
| SHA-256, UUID, Base64, `subtle` | Digests, unique IDs, wire encoding and constant-time comparisons. | Hashes versus encryption; IDs versus authorization |
| `thiserror`, `anyhow`, tracing | Typed core errors, application error context and structured diagnostics. | Safe logs and errors without credentials or memory contents |

The [native memory contract](memory-mvp.md) defines search and pagination limits.
BM25 scores measure query relevance; they are not truth confidence. Queries use
English lexical retrieval. Semantic embeddings and graph reasoning remain roadmap
work, with separate quality and resource gates.

## Memory controller and model runtime

| Technology or mechanism | Job | Study more deeply |
| --- | --- | --- |
| Python 3 standard library | Optional HTTP adapter, lifecycle controller, CLI and MCP bridge. No pip package is required for these paths. | Bounded I/O, subprocess ownership, JSON validation, exception contracts |
| Scope/entity/attribute slots | Stable fact identity across changing values. Hashed keys avoid putting raw labels in tombstones. | Normalization, entity ambiguity, isolation and identity collisions |
| Source quotes and event time | Preserve where a fact came from and when it was observed. | Grounding, temporal truth, observation time versus write time |
| Revisions and per-slot receipts | Conditional corrections and exact replay handling. | Idempotence, lost updates, concurrent writers, partial batch failure |
| Tombstones and semantic expiry | Forget removes managed content and blocks replay. `valid_until_ms` hides expired facts without deleting retry protection. | Delete semantics, revival prevention and retention policy |
| OpenCode | Existing agent runtime and connected model provider. It selects deterministic controller tools through MCP. | Agent permissions, fresh sessions, context assembly, tool-use failures |
| Optional Ollama | Explicit local-model extraction and current-turn chat examples. Capture previews proposals before application. | Structured output, grounding checks, model locality and failure handling |

The service does not make model calls. Model output still needs deterministic
validation, and a grounded quote does not prove the model interpreted it correctly.
OpenCode's provider receives the prompt and returned memory used in that session;
choose a local provider when inference must stay on your device.

The controller has finite per-slot evidence capacity. It cannot compact evidence
or restore a forgotten slot yet. Native TTL must be disabled for its durable
namespace. [Exact limits and recovery steps](memory-controller.md#limits-and-recovery).

## Website, tooling and evaluation

| Technology | Job |
| --- | --- |
| Astro + TypeScript | Static pages, typed route registry and report-backed evidence pages |
| Markdown, unified, remark and GFM | One source for guides, HTML pages and agent-readable exports |
| Plain CSS + self-hosted Geist | Responsive layout and typography without a UI framework |
| Pagefind | Browser-side search over built static pages |
| Cloudflare Workers static assets + Wrangler | Publish the website and its exports; this deployment has no hosted memory backend |
| Miniflare/workerd | Local Worker preview and behavior checks |
| Git + GitHub Actions | Source history, review and separate core/site/packaging checks |
| rustfmt, Clippy, Rust tests | Formatting, static diagnostics and storage/API invariant verification |
| Python unittest, fake clocks and isolated real-node smoke | Focused controller risks, transports, permissions and restart behavior |
| Prettier, Astro check, TypeScript and export verification | Site style, types, routes, assets and internal links |
| Optional evaluation environment | Dataset retrieval and model QA, with a spending ledger and separate dependencies; it is outside the memory service |

[Website publication](website.md) and [evaluation policy](evaluation-policy.md)
describe their separate validation boundaries. A retrieval score, model test,
server restart and deployed page establish different things.

## Small exercises that teach the design

1. Read the transaction that updates a memory and explain how it removes old
   search postings. Then trace a quota failure without changing engine code.
2. Save a preference, submit an older contradiction, then correct the current
   value with its inspected revision. Explain each receipt.
3. Retry the same proposal. Change its payload while keeping its source ID.
   Explain why one is accepted and the other rejected.
4. Forget a fact, restart, and retry its old proposal. Inspect the tombstone
   and explain why native TTL would make this unsafe.
5. Start a fresh OpenCode session and inspect the actual tool calls. Distinguish
   retrieved memory from anything the model guessed.

Use temporary state for these exercises. [The controller guide](memory-controller.md)
provides runnable commands and an isolated smoke scenario.
