# Historical KV browser demo

Archived verification notes. Use [the current memory demo](live-demo.md) for current behavior.


[Open the demo](https://instantkv.com/demo/). No account or model API key is needed.
The default mode replays recorded Mac KV measurements.
Live VPS mode writes temporary synthetic records to the Rust service.
The page counts only acknowledged writes.

To test live storage:

1. Select **Live VPS** and a storage mode.
2. Set the synthetic context and start the writer.
3. Clear local context after writes complete.
4. Select a record index and recall it in the reader.
5. Open the reader in a new tab to verify independent retrieval.

The reader-tab link contains only a session locator. It does not contain the saved value.
This demo uses the raw KV API. The [structured-memory benchmark](performance.md) measures the new retrieval API.

## Recorded Mac replay

The recording uses an Apple M4 Pro with 24 GiB memory.
Three cache runs stored 100,000 records each; three durable runs stored 10,000 each.
They completed 330,000 acknowledged writes and 24 exact reads with zero errors.
Replay selects the median-throughput run for each mode.
[Raw reports and reproduction](demo-results/2026-10-02-mac/README.md).

Animation plays at 2× speed. Performance figures use the original measured times.
During playback, p50/p99 describe the latest batch. At completion, they describe the whole run.

Cloudflare serves the static recording.
The browser caches four exact responses per mode: first, quarter, middle and last.
Recorded recall copies a response from that cache and makes no storage request.
The page separates browser lookup time from recorded Rust HTTP read time.
Clearing the displayed context does not remove the recording.

Live VPS tests retrieval from storage. A live reader tab passes only its locator.
A recorded reader tab loads its own recording copy.

The client cache timer measures lookup and copy in browser memory.
It excludes the network, Rust storage and rendering.
Browsers [reduce clock precision](https://developer.mozilla.org/en-US/docs/Web/API/Performance/now#security_requirements), so short operations can have equal start/end timestamps.
The page shows **Below timer resolution** for that case.
Positive values below display precision show **<0.001 ms**. Recorded backend timing remains unchanged.

```text
Mac recorder → real Rust PUT/GET → raw reports + verified response samples
                                      ↓ select median throughput run
Cloudflare static recording → browser cache → 2× trace playback / saved recall
```

RAM median: **42,517 writes/s**; PUT p50/p99: **0.328/0.726 ms**.
Durable median: **225 writes/s**; PUT p50/p99: **70.349/81.229 ms**.
Durable writes were slower on this Mac than in the earlier VPS demo.
Both datasets retain their original conditions. Local HTTP does not predict public HTTPS latency.

## Actual storage path

```text
Browser writer / independent reader
  │ HTTPS · same-origin /api/demo/*
  ▼
Cloudflare Worker + Static Assets (instantkv.com)
  │ bounded request, origin check, per-IP rate limit, private gateway credential
  ▼ Workers VPC service binding · encrypted Cloudflare Tunnel
Private loopback → isolated demo coordinator on Rove
  │ synthetic fixtures · 512 records/batch · 16 concurrent HTTP operations
  ▼
instantKV Rust HTTP API · separate demo container
  ├─ demo_cache     → RAM + FIFO + 15-minute TTL
  └─ demo_knowledge → redb immediate transactions + 15-minute TTL
```

Cloudflare serves the site and forwards live-demo requests.
The Rust service stores cache records in RAM and durable records in redb on the VPS.
A Node coordinator generates synthetic values and groups writes into batches.
Every live value is stored and read through instantKV.

## What the numbers mean

| Metric               | Measurement                                                                                                                                           |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Acknowledged records | Successful Rust PUT responses, advanced only when the complete batch succeeds                                                                         |
| Payload written      | Actual UTF-8 bytes of JSON values; key/storage/transport overhead excluded                                                                            |
| End-to-end rate      | Acknowledged records divided by accumulated successful browser write-request time; pauses and session creation excluded                               |
| Backend p50/p99      | Percentiles across every successful coordinator-to-Rust PUT in batches measured by this tab; includes HTTP and response parsing, not engine-only time |
| Live trace           | Browser round-trip for each successful 512-record batch; includes Cloudflare, TLS, network, batching and parsing                                      |
| Read round-trip      | Browser request through Cloudflare to the coordinator and back                                                                                        |
| Backend HTTP read    | Coordinator-to-Rust GET plus JSON parsing                                                                                                             |
| Exact verification   | Fetched JSON matches the generated value for that record                                                                                              |
| Failed requests      | Rejected browser API responses; failed batch replies also include their backend failure count                                                         |

Context length counts characters in the content field. The complete JSON record is larger.
Agent IDs cycle across 64 synthetic workers. Those labels do not provide namespace isolation.
The [CLI swarm demo](demo.md) tests worker isolation and checkpoint recovery.
Public-demo timing varies with location, server load and other visitors.

## Recorded live verification

On 2026-10-01, the deployed browser demo wrote **100,000 cache records / 68.25 MiB**
with zero failed API requests and zero JavaScript/CSP errors. First, middle and
last exact reads, pause/resume, context clearing, independent-tab recall and
390px mobile layout passed. [Raw cache verification report](demo-results/2026-10-01-cloudflare-cache.json).

Durable mode also wrote **10,000 records / 6.82 MiB** with zero failed API requests
and zero browser errors. After clearing local context, record 9,999 was retrieved
and exactly verified. [Raw durable verification report](demo-results/2026-10-01-cloudflare-durable.json).

| Public demo run           | Records |   Payload | End-to-end rate | Backend HTTP PUT p50 / p99 |
| ------------------------- | ------: | --------: | --------------: | -------------------------: |
| RAM cache                 | 100,000 | 68.25 MiB |   854 records/s |            5.78 / 88.61 ms |
| Immediate durable storage |  10,000 |  6.82 MiB |   330 records/s |          26.36 / 127.60 ms |

These are individual public-demo runs on a shared VPS with explicit CPU limits.
They remain separate from controlled three-run benchmarks.

## Resource and data boundaries

RAM workloads allow 1,000–100,000 records. Durable workloads allow at most 10,000.
Sessions expire after 15 minutes, with at most 12 sessions and two concurrent batches.
Each batch sends at most 16 backend requests in parallel.

Use only synthetic data. Never submit secrets or production memory.

The RAM namespace allows 128 MiB of logical data and 150,000 records. It can evict older records.
Durable storage allows 64 MiB and 30,000 records; excess writes fail.
Both use indexed expiry cleanup.
The memory container has a 512 MiB/one-CPU limit; the coordinator has a 192 MiB/half-CPU limit.
Quotas count logical key/value bytes, not all process overhead.

Session locators are random 192-bit bearer capabilities.
A locator permits reading that session until expiry. It is not production identity or tenant authorization.
Engine, gateway and tunnel credentials remain server-side.
The private VPC binding exposes only the coordinator's loopback port.
There is no public HTTP origin route or DNS record.

The Worker permits four fixed operations and validates origins and body size.
Its 240-requests/minute/IP limit applies per location; shared networks can share that limit.
The gateway applies global session and concurrency limits for this deployment.
This sandbox is separate from a future managed service.

## Reproduce on your own machine

1. Build/package the Rust image using the repository's Docker quick-start.
2. Copy `demo/` to a dedicated deployment directory. Create an ignored `.env` with
   independently generated `INSTANTKV_DEMO_TOKEN` and `DEMO_GATEWAY_TOKEN` secrets.
3. Run `docker compose -f demo/compose.yaml up -d` from the repository root. The
   image `instantkv:local` must already exist. The demo creates a separate volume.
4. Create a remotely managed Cloudflare Tunnel, keep its connector token in a
   private `demo/.tunnel-token` owned by UID 65532, and run Compose with
   `--profile cloudflare`. Create a Workers VPC HTTP service targeting
   `127.0.0.1:8098` through that tunnel. Set its `service_id` for `DEMO_BACKEND` in
   both Wrangler environments. `DEMO_ORIGIN` supplies the internal Host header;
   the binding configuration fixes the actual destination. No public DNS needed.
5. In `site/`, use `npx wrangler secret put DEMO_GATEWAY_TOKEN --env production`
   and enter the same gateway secret. Then `npm run deploy:domain`.

For local preview, use `npm run build`, `npm run preview` and provide the gateway
secret through an ignored `site/.dev.vars`. The VPC binding uses remote mode, so
Wrangler authentication and the running tunnel are required. Keep authentication enabled on the
engine. Do not expose the Rust container port or grant the demo access to existing
agent namespaces. Stop the isolated Compose project to disable the demo; the docs
remain usable when the proxy returns a temporary-unavailability response.

The connector uses cloudflared 2026.9.3. VPC requires QUIC and outbound UDP port 7844.
This integration is a beta; the self-hosted HTTP API remains separate.
[Official VPC setup](https://developers.cloudflare.com/workers-vpc/get-started/) ·
[Tunnel requirements](https://developers.cloudflare.com/workers-vpc/configuration/tunnel/).

Run `cd site && npm test` for coordinator/proxy tests.
They cover credentials, limits, exact integrity, invalid indices and partial batch failure/retry.
Before deployment, test cache/durable writes, pause/resume, cleared context, independent recall, failure states and mobile layout.

## Website design references

The initial demo reviewed [Upstash Redis](https://upstash.com/redis), [Turso](https://turso.tech) and [Valkey](https://valkey.io/).
Later design work reviewed [Redis](https://redis.io/) and Valkey.
The current site uses a minimal white layout and neutral typography.
Its homepage leads with local memory, runnable examples and measured results.
Phone integration and device targets remain planned.
