# Benchmark: HTTP request paths

Measured on Rove on 2026-10-01, using verified source
[`28412f4`](https://github.com/maskjelly/instantKV/tree/28412f4e209b98c522846da79d2489f1d970e91f).
Three runs per profile; **157,500 successful measured requests, zero errors**.
Table values are medians of the three run results, not pooled percentiles.

| Workload | Requests/run | Concurrency | Successful req/s | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|---:|---:|---:|
| Scratch GET | 20,000 | 16 | 3,708 | 1.88 | 10.55 | 47.36 |
| Knowledge GET | 20,000 | 16 | 4,010 | 1.73 | 9.11 | 47.20 |
| Durable PUT | 2,000 | 8 | 744 | 5.80 | 51.62 | 57.65 |
| Checkpoint save | 500 | 8 | 474 | 8.98 | 56.08 | 64.97 |
| Restore | 10,000 | 16 | 3,324 | 2.24 | 12.25 | 48.54 |

## Environment and interpretation

4 KVM vCPUs, reported Common KVM processor at about 2.49 GHz; 7.56 GiB available
physical RAM. Ubuntu 20.04 host, Linux 5.15, Docker 28.1.1 / Compose 2.35.1;
Debian 12 runtime image. Namespace-scoped auth was enabled. Durable writes used
redb 4.3.0 immediate commits throughout.

This was a **shared, busy VPS** with existing services and shortener load generators
running. Host load averages were 4.24 before and 5.44 after on four vCPUs. We did
not stop those services. Client and server shared a container and CPU over loopback
HTTP/1.1 keep-alive, without pipelining. These are workload observations, not an
isolated engine benchmark, public HTTPS capacity, maximum throughput or an SLA.
The roughly 40–65 ms tails remain visible instead of being hidden behind p50.

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

The post-run Docker memory snapshot was 10.3 MiB and the database file 3,379,200
bytes. This is a snapshot, not peak RSS or a long-term storage-growth test.

[All 15 raw reports](benchmarks/2026-10-01-rove/) and
[environment metadata](benchmarks/2026-10-01-rove/environment.json)
are committed alongside this page. CPU metadata retains only benchmark-relevant
fields. Every report records request counts, duration, successful throughput,
latencies, transport and durability description. Binary/image hashes are in the
metadata; source files were checked against the recorded commit before running.

## Reproduce

Use an isolated default-profile server. The script repeats all five workloads:

```sh
INSTANTKV_BIN=./scripts/kv.sh ./scripts/benchmark-suite.sh /absolute/results
# For a locally installed binary:
INSTANTKV_BIN=instantkv ./scripts/benchmark-suite.sh /absolute/results
```

Checkpoint/restore runs retain snapshots; do not use a busy production namespace.
The default suite adds 3,096 checkpoint namespace records (bundle/pointer pairs)
and keeps them for inspection. Run larger/concurrent workloads only within your
configured quota. Preserve the config, hardware, revision and load conditions
when sharing numbers.

Next measurements: larger key populations, real capsule/reference distributions,
repeated-session saves, expiry backlogs, contention curves, longer runs, peak RSS
and disk growth. These runs do not prove those workloads.
