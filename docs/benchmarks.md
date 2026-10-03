# Benchmark: structured memory

The current benchmark measures the memory API: save, recall, browse, exact read and forget.
The [performance guide](performance.md) gives measured results and separate device targets.
[Raw report and all latency samples](benchmarks/2026-10-04-search/mac-arm64.json).

## More retrieval workloads

The [local retrieval suite](benchmarks/2026-10-04-search/README.md) tests NFCorpus,
ArguAna, LoCoMo evidence turns and a fixed LongMemEval-S session pilot.
It keeps default query budgets and counts rejected questions as misses.
The [short article](memory-benchmark-notes.md) explains the measured tradeoffs.
These scores do not measure answer quality or the hosted Supermemory pipeline.

## Retrieval and recovery

Three fresh local-profile databases contain 10,000 memories each.
Each memory has 512-byte content, a topic, one tag, event time and JSON metadata.
The workload uses 20 topics and four tags.

Requests use authenticated loopback HTTP/1.1 with keep-alive, concurrency one.
Queries have 20 warmups and 300 timed calls per workload.
They return up to 10 memories with a 16 KiB response budget.
Durable saves keep immediate commits enabled.

The script measures:

- New memory saves, including index updates.
- Topic, tag, time, combined and unfiltered browse queries.
- One bounded page of a sparse literal keyword query.
- Exact-key reads and revision-checked deletes.

After an abrupt process exit, every saved field is compared with its original receipt.
Cursor continuation finds the oldest keyword match.
Then 300 memories are deleted. A complete browse verifies exactly 9,700 remaining memories.
The real MCP bridge is checked separately, outside HTTP timing. No model runs.

Percentiles use actual request samples. Reported ranges cover three runs.
Website chart medians use three run percentiles; they do not pool samples.
RSS is sampled process memory, not the true peak.
These warm synthetic tests exclude inference, public HTTPS, battery use and phones.
Abrupt process termination does not test power loss.

```sh
cargo build --release --locked -p instantkv
python3 scripts/memory-bench.py --records 10000 --runs 3 --queries 300 \
  --output /tmp/instantkv-memory-benchmark.json
```

The script creates private temporary state and removes it afterward.
Preserve the source revision, binary hash, hardware, cache state and transport with results.

## Browser demo recording

The [browser demo](https://instantkv.com/demo/) calls the same structured-memory API.
Recorded mode uses saved responses from three 10,000-memory runs.
The recorder uses 16 concurrent saves, 512-memory batches and one fresh dedicated database.
This queued workload has different latency from the sequential benchmark.

Each run preserves four exact reads, six query types, the next browse page,
a revision-checked deletion receipt and an empty query proving index removal.
Recorded mode selects the median-throughput run and makes no new storage calls.

```sh
node demo/record.mjs /tmp/instantkv-memory-recordings
```

[Recording conditions and three raw runs](demo-results/2026-10-03-memory/README.md).
Live browser timing includes the public network. Recorder timing uses local HTTP.
Neither measures engine-only time or model quality.

Historical raw KV data stays in the repository under dated directories.
It is not used for current product metrics.

## Ranked document recall

[BEIR SciFact comparison](benchmarks/2026-10-04-search/README.md): BM25 document
ranking, full queries, raw relevance metrics and measured indexing costs.
The browser recordings remain demonstrations of literal filters, not ranked-search evidence.
