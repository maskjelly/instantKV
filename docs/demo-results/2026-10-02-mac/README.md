# Mac demo measurements — 2026-10-02

Apple M4 Pro, 14 physical cores, 24 GiB RAM, macOS 27.0. Published instantKV 0.1.2
binary, runtime source `6eceb8bdd2450cc9977d0fd3c4b3627a9bf0a032`.
[Environment and binary SHA-256](environment.json).
The report's `recorder_source` identifies the checkout base at capture; the new
recorder was committed afterward in `6283ed7`. The coordinator itself was
unchanged from that checkout. The published binary has its own runtime source
and SHA-256, recorded separately.

The real demo coordinator wrote unique synthetic records through the Rust HTTP
API: three runs of 100,000 RAM records and three of 10,000 durable records.
**330,000 acknowledged writes, 24 exactly verified reads, zero errors.**
This ran directly on the Mac, without Docker CPU limits, Cloudflare or public
network latency. Other applications stayed open. Each run used a new session;
all six shared one initially empty, dedicated instance. Session creation and
reads are outside write timing; no separate warmup was performed.

| Mode | Run 1 writes/s | Run 2 writes/s | Run 3 writes/s | Replay run | Whole-run PUT p50 / p99 |
|---|---:|---:|---:|---:|---:|
| RAM cache | 39,889 | 42,517 | 43,025 | 2 | 0.328 / 0.726 ms |
| Immediate durable storage | 225 | 218 | 233 | 1 | 70.349 / 81.229 ms |

Replay selects the median **throughput run**, and keeps that run's actual
percentiles and saved responses. It does not combine different runs' best
metrics. Playback takes half the recorded time; displayed measurements are
unchanged. The cached browser lookup is measured separately and is not a Rust
read. Only four saved responses per mode are included.

## Measurement boundaries

- 512 records per batch, 16 concurrent coordinator-to-Rust requests, HTTP/1.1
  keep-alive. Timing includes HTTP and JSON parsing, not just storage operations.
- Throughput divides the acknowledged count by the sum of successful local
  client-to-coordinator write-request durations. It excludes pauses, session
  setup and client work between batches. It is not total wall-clock throughput.
- PUT percentiles include every successful backend operation in the run. Raw
  reports retain all per-operation and per-batch timings.
- Each content field is 512 characters. Full JSON payload is about 715 bytes;
  payload totals exclude keys, metadata and transport overhead.
- RAM retains at most 150,000 entries / 128 MiB; FIFO can evict older sessions.
  Durable storage retains at most 30,000 entries / 64 MiB. All records have a
  900-second TTL. First, quarter, middle and last reads occur immediately after
  each run and verify the stored JSON against the original fixture.
- Durable PUT waits for redb's immediate commit. These Mac durable results are
  slower than the earlier public VPS demo. Hardware alone does not predict
  performance; workload, filesystem and deployment conditions matter.
- No claim about maximum throughput, public HTTPS capacity, model memory quality
  or another machine's speed follows from this test. Client caching accelerates
  replay, not the storage engine.

## Reproduce

From the repository root, with Node.js 24+ and the release binary:

```sh
INSTANTKV_BIN=/absolute/path/to/instantkv node archive/browser-demo/record.mjs /absolute/results
node --test archive/browser-demo/replay-data.test.mjs
```

The recorder is macOS-specific for hardware discovery. Port 18089 must be free.
It creates private temporary credentials and data, binds both services to
loopback, stops its own processes and removes its temporary state when finished.
It aborts on any failed write or read. Failed measurements must not be presented
as zero-error runs. The replay tests check the committed dataset; new reports
can be checked with `validateRecording` from `archive/browser-demo/replay-data.mjs`.

Raw reports: [cache 1](cache-1.json), [cache 2](cache-2.json),
[cache 3](cache-3.json), [durable 1](durable-1.json),
[durable 2](durable-2.json), [durable 3](durable-3.json).
