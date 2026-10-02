# Performance: measured and planned

Status: source MVP, 2026-10-03. The figures below describe the memory service,
excluding the LLM, inference time and caller. Targets are engineering goals,
not promised performance on any ARM device.

## Structured memory measured on a Mac

Apple M4 Pro, 24 GiB unified memory, macOS 27.0. Native release binary.
Three fresh local-profile databases, 10,000 memories each. Every memory has
512 bytes of content plus an envelope, topic, one tag and custom metadata.
Twenty topics / four tags. Sequential authenticated loopback HTTP/1.1 keep-alive,
concurrency one. Twenty warmup queries per workload, then 300 measured queries.
Read pages request 10 memories and a 16 KiB response budget.

| Measurement | Observed across three runs |
|---|---|
| Native binary | 8.0 MiB |
| Idle server RSS | 6.17–6.20 MiB |
| Largest sampled server RSS | 19.5 MiB |
| Topic query p95 | 0.134–0.190 ms |
| Tag query p95 | 0.134–0.153 ms |
| Time-range query p95 | 0.131–0.140 ms |
| Topic + tag + keywords p95 | 0.133–0.141 ms |
| Browse p95 | 0.334–0.386 ms |
| Keyword first-page p95 | 1.267–1.530 ms |
| Immediate durable save p95 | 5.686–5.885 ms |
| Physical database after workload | 25.3 MiB per run |
| Exact memories recovered after abrupt restart | 10,000/10,000 per run; 30,000 total |

[Raw report, all latency samples, hardware and binary hash](benchmarks/2026-10-03-memory/mac-arm64.json).
RSS samples are not peak RSS. These are warm, synthetic queries on one machine;
they do not establish inference quality, battery cost or mobile performance.
The sparse keyword measurement is **one 1,000-candidate page with no result**,
not complete search. Finding the oldest matching memory took ten pages. The
script separately verifies complete recovery and cursor traversal after restart.
Process termination is not power-loss or disk-failure testing.

Reproduce from a source checkout, with Python 3 and Rust 1.98+:

```sh
cargo build --release --locked -p instantkv
python3 scripts/memory-bench.py --records 10000 --runs 3 --queries 300 \
  --output /tmp/instantkv-memory-benchmark.json
```

The script creates fresh temporary setups, writes real memories, samples server
RSS, kills/restarts its own child processes, verifies every saved field and removes
temporary databases. It does not download models, change your running node or
retain credentials. Initial source compilation may download dependencies.

## Next device targets — not yet measured

Validate these goals on a named 64-bit Linux ARM board with 4 GiB RAM and local
flash storage, then scope phone targets with the native app. Use the same
10,000-memory workload above. Report storage type, OS, model/runtime overhead
and cold versus warm results. A goal can fail; publish the result and adjust it.

| Metric | Initial goal | Validation required |
|---|---|---|
| Idle memory service RSS | ≤12 MiB | Repeated process samples; add true peak measurements |
| Loaded memory service RSS | ≤32 MiB | Writes, indexed reads and bounded keyword scans |
| Indexed recall p95 | ≤5 ms | Topic/tag/time pages, 10 results, concurrency one |
| Immediate durable save p95 | ≤20 ms | Record + indexes; keep synchronization enabled |
| Recovery correctness | Every acknowledged memory retained | Repeated abrupt exits; then disk-full/commit fault injection |
| Context budget | Default page ≤16 KiB | Include content, metadata, timestamps and cursor |

The Mac runs meet these latency/RSS goals on that Mac. The goals remain unverified
on the ARM board and phones. No portable peak-RAM cap, battery target or promised
throughput is claimed. Component budgets do not add up to a process RSS cap.

## What comes after the MVP

1. **Real local-agent evaluation:** save a fact, clear prompt context, restart
   the memory service, recall by topic/time and use it correctly. Measure tool
   success and task correctness separately from storage latency.
2. **Native mobile integration:** in-process Swift/Kotlin bindings, sandbox data
   paths, app suspension/relaunch, backup, encryption design and battery profiling.
   An ARM64 Mac/Linux binary alone does not prove native phone support.
3. **Larger memories:** repeat at 100,000 records with an explicitly larger quota;
   measure index/disk growth, cold reads, concurrent writers and expiry backlog.
4. **Optional better retrieval:** ranked lexical search, then user-supplied local
   embeddings only when task evaluations show a need. Measure index size, model
   download and recall quality before setting a footprint expectation.

Earlier [KV/cache benchmarks](benchmarks.md) remain historical evidence for their
own APIs and workloads. The browser replay shows those KV writes, not the new
indexed-memory API. Do not transfer its throughput figure to structured recall.
