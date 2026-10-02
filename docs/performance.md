# Performance: measured and planned

Status: source MVP. Updated: 2026-10-03.
The results measure the memory service. They exclude the LLM, inference time and caller.
Targets are engineering goals for a defined workload.

## Structured memory measured on a Mac

| Workload setting | Value                                                     |
| ---------------- | --------------------------------------------------------- |
| Hardware         | Apple M4 Pro; 24 GiB unified memory                       |
| Operating system | macOS 27.0                                                |
| Binary           | Native release build                                      |
| Databases        | Three fresh local-profile databases                       |
| Memories         | 10,000 per run                                            |
| Content          | 512 bytes per memory, plus envelope and metadata          |
| Labels           | 20 topics; four tags; one tag per memory                  |
| Requests         | Authenticated loopback HTTP/1.1 with keep-alive           |
| Concurrency      | One sequential request                                    |
| Queries          | 20 warmup queries, then 300 measured queries per workload |
| Read page        | 10 memories; 16 KiB response budget                       |

| Measurement                                   | Observed across three runs          |
| --------------------------------------------- | ----------------------------------- |
| Native binary                                 | 8.0 MiB |
| Idle server RSS                               | 6.17–6.22 MiB |
| Largest sampled server RSS                    | 19.4 MiB |
| Topic query p95                               | 0.129–0.134 ms |
| Tag query p95                                 | 0.131–0.134 ms |
| Time-range query p95                          | 0.130–0.133 ms |
| Topic + tag + keywords p95                    | 0.132–0.133 ms |
| Browse p95                                    | 0.362–0.382 ms |
| Keyword first-page p95                        | 1.241–1.275 ms |
| Immediate durable save p95                    | 5.680–5.862 ms |
| Physical database after workload              | 25.3 MiB per run                    |
| Exact memories recovered after abrupt restart | 10,000/10,000 per run; 30,000 total |

[Raw report, latency samples, hardware and binary hash](benchmarks/2026-10-03-memory/mac-arm64.json).
p95 is the time within which 95% of measured operations complete.
RSS means resident set size: process memory reported by the operating system.
The samples do not measure peak RSS.
Warm synthetic queries on this Mac do not measure model quality, battery use or phone performance.

The sparse keyword result measures one 1,000-candidate page with no match.
Finding the oldest matching memory required ten pages.
The script verifies recovery and cursor continuation after restart.
Process termination does not test power loss or disk failure.

To reproduce the results, use Python 3 and Rust 1.98 or later:

```sh
cargo build --release --locked -p instantkv
python3 scripts/memory-bench.py --records 10000 --runs 3 --queries 300 \
  --output /tmp/instantkv-memory-benchmark.json
```

The script creates temporary databases and writes real memories.
It samples server RSS, terminates its server processes and restarts them.
It verifies every saved field and removes the temporary databases.
It does not change your running node or retain credentials.
Source compilation can download dependencies. The script does not download a model.

Exact-key read p95: **0.103–0.104 ms**.
Revision-checked forget p95: **5.287–5.773 ms**.
After recovery, 300 memories per run were deleted. A full browse verified exactly
9,700 remaining memories per run and no deleted index results.

## Next device targets — not yet measured

1. Select a 64-bit Linux ARM board with 4 GiB RAM and local flash storage.
2. Run the 10,000-memory workload above.
3. Record the storage type, operating system and model/runtime overhead.
4. Report cold and warm results separately.
5. Publish failed targets as well as successful targets.

Phone targets need separate tests in a native app.

| Metric                     | Initial goal                       | Validation required                                          |
| -------------------------- | ---------------------------------- | ------------------------------------------------------------ |
| Idle memory service RSS    | ≤12 MiB                            | Repeated process samples; add true peak measurements         |
| Loaded memory service RSS  | ≤32 MiB                            | Writes, indexed reads and bounded keyword scans              |
| Indexed recall p95         | ≤5 ms                              | Topic/tag/time pages, 10 results, concurrency one            |
| Immediate durable save p95 | 5.680–5.862 ms |
| Recovery correctness       | Every acknowledged memory retained | Repeated abrupt exits; then disk-full/commit fault injection |
| Context budget             | Default page ≤16 KiB               | Include content, metadata, timestamps and cursor             |

The Mac runs meet these latency and RSS targets on that Mac.
The targets remain unverified on the ARM board and phones.
There is no portable peak-RAM cap, battery target or throughput guarantee.
Component limits do not cap total process RSS.

## What comes after the MVP

1. **Local-agent evaluation:** save a fact, clear context and restart the service.
   Verify that the agent retrieves and uses the fact correctly.
   Measure tool success and task correctness separately from storage latency.
2. **Native mobile integration:** add Swift/Kotlin bindings and sandbox data paths.
   Test app suspension, restart, backup, encryption design and battery use.
3. **Larger workloads:** repeat with 100,000 records and an explicit larger quota.
   Measure index growth, cold reads, concurrent writes and expiry backlog.
4. **Optional retrieval:** evaluate ranked keyword search before local embeddings.
   Measure task quality, index size, model download size and resource use.

The [current browser demo](live-demo.md) uses the same structured-memory API.
Its recorder uses 16 concurrent saves; the benchmark above uses concurrency one.
[Benchmark methodology](benchmarks.md) explains both workloads.
