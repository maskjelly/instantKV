# Historical raw KV benchmarks

Archived workload notes. Use [current memory benchmarks](benchmarks.md) for the current product.
The raw reports below remain unchanged.


The [structured-memory results](performance.md) cover three 10,000-memory runs, indexed retrieval, RSS samples and exact restart recovery.
The raw KV and cache results below use different APIs and workloads.
Their throughput does not measure structured-memory queries.

The [earlier local-profile test](local-first.md#measured-mac-footprint) records raw KV binary size, sampled RSS and restart recovery.

## Mac demo: 330,000 writes, zero errors

Six demo runs used an Apple M4 Pro with 24 GiB memory on 2026-10-02.
Three RAM runs wrote 100,000 records each; three durable runs wrote 10,000 each.
All 24 sampled reads matched their original values.

| Median-throughput run | Writes/s |   PUT p50 |   PUT p99 |
| --------------------- | -------: | --------: | --------: |
| RAM                   |   42,517 |  0.328 ms |  0.726 ms |
| Durable               |      225 | 70.349 ms | 81.229 ms |

These tests created unique records through local HTTP, without public-network latency or container CPU limits.
They differ from the hot-key tests below.
Replay runs at 2× animation speed and caches four saved responses per mode.
Measured latency and throughput remain unchanged.
[Conditions and all six reports](demo-results/2026-10-02-mac/README.md).

## Rove HTTP workloads — 2026-10-01

Measured on Rove on 2026-10-01, using verified source
[`28412f4`](https://github.com/maskjelly/instantKV/tree/28412f4e209b98c522846da79d2489f1d970e91f).
Three runs per profile; **157,500 successful measured requests, zero errors**.
Table values are medians of the three run results, not pooled percentiles.

| Workload        | Requests/run | Concurrency | Successful req/s | p50 ms | p95 ms | p99 ms |
| --------------- | -----------: | ----------: | ---------------: | -----: | -----: | -----: |
| Scratch GET     |       20,000 |          16 |            3,708 |   1.88 |  10.55 |  47.36 |
| Knowledge GET   |       20,000 |          16 |            4,010 |   1.73 |   9.11 |  47.20 |
| Durable PUT     |        2,000 |           8 |              744 |   5.80 |  51.62 |  57.65 |
| Checkpoint save |          500 |           8 |              474 |   8.98 |  56.08 |  64.97 |
| Restore         |       10,000 |          16 |            3,324 |   2.24 |  12.25 |  48.54 |

## Environment and interpretation

4 KVM vCPUs, reported Common KVM processor at about 2.49 GHz; 7.56 GiB available
physical RAM. Ubuntu 20.04 host, Linux 5.15, Docker 28.1.1 / Compose 2.35.1;
Debian 12 runtime image. Namespace-scoped auth was enabled. Durable writes used
redb 4.3.0 immediate commits throughout.

The VPS was shared and busy. Existing services and load generators stayed active.
Load averages were 4.24 before and 5.44 after, on four vCPUs.
Client and server shared a container and used loopback HTTP/1.1 with keep-alive and no pipelining.

The results do not measure public HTTPS capacity, isolated engine speed or maximum throughput.
The table includes p99 latency as well as median latency.

## Workload details

- GET/PUT: 512-byte JSON strings; hot keys, one key per worker (16 read keys,
  eight write keys). Durable GET is cached data in the embedded engine/OS path.
- PUT: repeated updates, immediate commit acknowledgement; not bulk ingestion.
- Checkpoint: fixed built-in capsule, no references, a fresh ID/session each time;
  bundle and new latest pointer committed together. 500 measured saves per run.
- Restore: fixed capsule, no references, default 32 KiB response budget; 16 seed
  sessions per run. Detailed referenced record fetching is a separate operation.
- Seed/warmup/cleanup are outside timing. Initial concurrent fan-out can create
  additional connections inside the measured interval. Percentiles include all
  measured responses; there were no failures in these runs.
- Ordinary keys are deleted afterward. Checkpoint records remain in the disposable
  benchmark volume. The usable VPS instance gets a separate volume and credentials.

The post-run Docker memory snapshot was 10.3 MiB. The database file was 3,379,200 bytes.
These observations do not measure peak RSS or long-term database growth.

[All 15 reports](benchmarks/2026-10-01-rove/) and [environment metadata](benchmarks/2026-10-01-rove/environment.json) are committed.
Reports include request counts, durations, throughput, latency, transport and durability.
Metadata includes binary/image hashes. Source files matched the recorded commit before the tests.

## Reproduce

Use an isolated default-profile server. The script repeats all five workloads:

```sh
INSTANTKV_BIN=./scripts/kv.sh ./scripts/benchmark-suite.sh /absolute/results
# For a locally installed binary:
INSTANTKV_BIN=instantkv ./scripts/benchmark-suite.sh /absolute/results
```

Use a disposable checkpoint namespace; the suite retains checkpoint records.
Keep requests within the configured quotas.
Preserve the configuration, hardware, source revision and host load with your results.

The default suite adds 3,096 checkpoint records, including bundles and pointers.

Planned tests cover larger key sets, realistic capsules and references, repeated sessions and expiry backlogs.
Longer runs must measure contention, peak RSS and disk growth.
