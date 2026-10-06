# Current memory demo measurements — 2026-10-03

Three runs use the current structured-memory API on an Apple M4 Pro with 24 GiB RAM.
Each run saves 10,000 new memories. All 30,000 writes were acknowledged, with zero errors.
Four exact reads per run verify content, topic, tags, event time and JSON metadata.

The runs preserve six real query responses: browse, topic, tag, time, keywords and combined filters.
They also preserve the next browse page, a revision-checked deletion receipt and an empty
query proving the deleted event is absent from the index.

## Conditions

- Native release binary; runtime source revision and SHA-256 in every report.
- One fresh dedicated database, three sessions in sequence.
- Durable redb commits. Memory and index changes share a transaction.
- 512 ASCII characters of content, plus structured fields and envelope.
- Four topics and two session-scoped labels per run, plus a session isolation tag.
- Synthetic event time starts at 2026-10-03 00:00 UTC; events advance by one minute.
- Local HTTP/1.1 with keep-alive; 16 concurrent saves, batches of 512.
- No Cloudflare, public-network latency, model inference or container CPU limit.
- Other Mac applications remain running. Timing excludes session setup and later queries/deletion.

`elapsed_ms` is the sum of client write-batch round trips.
Throughput is acknowledged saves divided by that duration.
Backend percentiles use every actual per-memory HTTP latency sample.
These queued writes differ from the concurrency-one [memory benchmark](../../performance.md).

Recorded mode selects the median-throughput run and displays original responses and timings.
It makes no new storage requests. Clearing displayed context leaves the cached recording available.
The recorded delete receipt describes a deletion that ran during measurement; it does not delete live data.

## Reproduce

```sh
cargo build --release --locked -p instantkv
node archive/browser-demo/record.mjs /tmp/instantkv-memory-recordings
node --test archive/browser-demo/replay-data.test.mjs
```

The recorder uses private temporary storage and credentials. It removes them after completion.
The tests validate the committed reports. `validateRecording` in `archive/browser-demo/replay-data.mjs`
can validate new reports. Altered timings, missing acknowledgements and changed memory fields fail validation.

[Run 1](memory-1.json) · [Run 2](memory-2.json) · [Run 3](memory-3.json) · [Environment](environment.json).
