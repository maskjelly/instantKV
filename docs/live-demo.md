# Live memory demo

[Open the demo](https://instantkv.com/demo/). No account or model API key is
needed. The default mode replays a recorded Mac run. Select **Live VPS** to
choose RAM cache or durable storage, edit the synthetic context and start
the writer. The page displays only acknowledged writes. Clear local context,
choose a record index and recall it from the separate reader. **Open reader in
new tab** passes only a session locator. The new page uses it to fetch the saved
value from the Rust service.

## Recorded Mac replay

The default view uses actual measurements from an Apple M4 Pro / 24 GiB Mac.
Three 100,000-record cache runs and three 10,000-record durable runs completed
with **330,000 acknowledged writes, 24 verified reads and zero errors**. The
median-throughput run for each mode supplies its own trace, timings and saved
responses. [All reports and reproduction](demo-results/2026-10-02-mac/README.md).

The animation plays at 2× speed. Throughput and latency always use the original
measured times. During playback, p50/p99 describe the latest recorded batch;
completion shows the whole-run percentiles. There is no 50% performance uplift
or prediction about other hardware.

Cloudflare serves a static recording. The browser caches four exact storage
responses per mode: first, quarter, middle and last. Recall copies a saved
response from that cache; the page labels its lookup time separately from the
recorded coordinator-to-Rust GET time. It issues no storage request and writes
no records during replay. Clearing context clears only the displayed preview;
the recording remains cached. Use Live VPS to test retrieval from storage
independent of the browser. A recorded reader tab loads its own copy of the
static recording, whereas a live reader tab passes only its session locator.

The client cache timer covers finding and copying a saved response in browser
memory. It excludes the network, Rust storage and display rendering. Browsers
[reduce clock precision](https://developer.mozilla.org/en-US/docs/Web/API/Performance/now#security_requirements),
so a short lookup can return the same timestamp before and after the operation.
The demo shows **Below timer resolution** for that case. It does not display a
numeric zero or substitute an invented latency. Positive durations below the
display's precision show **<0.001 ms**; recorded backend timings stay unchanged.

```text
Mac recorder → real Rust PUT/GET → raw reports + verified response samples
                                      ↓ select median throughput run
Cloudflare static recording → browser cache → 2× trace playback / saved recall
```

RAM median: **42,517 writes/s**, PUT p50/p99 **0.328/0.726 ms**. Immediate durable
median: **225 writes/s**, PUT p50/p99 **70.349/81.229 ms**. Durable writes were
slower on this Mac than the earlier VPS demo. Local HTTP measurements cannot
predict public HTTPS latency; we preserve both datasets and their conditions.

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

Cloudflare serves the public site and forwards demo requests. The Rust service
runs on a VPS, storing cache records in RAM and durable records in redb. A small
Node coordinator generates synthetic values and groups writes into batches.
Every value is stored and read through instantKV.

## What the numbers mean

| Metric | Measurement |
|---|---|
| Acknowledged records | Successful Rust PUT responses, advanced only when the complete batch succeeds |
| Payload written | Actual UTF-8 bytes of JSON values; key/storage/transport overhead excluded |
| End-to-end rate | Acknowledged records divided by accumulated successful browser write-request time; pauses and session creation excluded |
| Backend p50/p99 | Percentiles across every successful coordinator-to-Rust PUT in batches measured by this tab; includes HTTP and response parsing, not engine-only time |
| Live trace | Browser round-trip for each successful 512-record batch; includes Cloudflare, TLS, network, batching and parsing |
| Read round-trip | Browser request through Cloudflare to the coordinator and back |
| Backend HTTP read | Coordinator-to-Rust GET plus JSON parsing |
| Exact verification | Fetched JSON matches the generated value for that record |
| Failed requests | Rejected browser API responses; failed batch replies also include their backend failure count |

Context length is a character count for the content field; the complete JSON
record is larger. Agent IDs cycle across 64 synthetic workers. The shared demo
does not model namespace isolation between those synthetic workers.
[The CLI swarm demo](demo.md) tests worker isolation and checkpoint recovery
after a restart. Use the [controlled benchmark page](benchmarks.md)
for the separate three-run, hardware-recorded measurements; public demo timings
vary with where you are, load on the shared server and other visitors.

## Recorded live verification

On 2026-10-01, the deployed browser demo wrote **100,000 cache records / 68.25 MiB**
with zero failed API requests and zero JavaScript/CSP errors. First, middle and
last exact reads, pause/resume, context clearing, independent-tab recall and
390px mobile layout passed. [Raw cache verification report](demo-results/2026-10-01-cloudflare-cache.json).

Durable mode also wrote **10,000 records / 6.82 MiB** with zero failed API requests
and zero browser errors. After clearing local context, record 9,999 was retrieved
and exactly verified. [Raw durable verification report](demo-results/2026-10-01-cloudflare-durable.json).

| Public demo run | Records | Payload | End-to-end rate | Backend HTTP PUT p50 / p99 |
|---|---:|---:|---:|---:|
| RAM cache | 100,000 | 68.25 MiB | 854 records/s | 5.78 / 88.61 ms |
| Immediate durable storage | 10,000 | 6.82 MiB | 330 records/s | 26.36 / 127.60 ms |

These are individual public demonstration runs on a shared VPS with explicit CPU limits;
the controlled three-run benchmark dataset remains separate.

## Resource and data boundaries

RAM workloads support 1,000–100,000 records; durable workloads stop at 10,000.
Sessions expire after 15 minutes, with at most 12 live sessions and two concurrent
write batches. Each batch performs up to 16 backend requests in parallel. Records
are synthetic and temporary: never submit secrets or production memory.

The RAM namespace is capped at 128 MiB/150,000 records and may evict older records.
Durable demo storage is capped at 64 MiB/30,000 records and rejects excess writes.
Both have indexed TTL cleanup. The memory container is limited to 512 MiB/one CPU;
the coordinator to 192 MiB/half a CPU. These limits isolate this demo from existing
agent deployments. Quotas measure key/value bytes, not all process overhead.

Session locators are randomly generated 192-bit bearer capabilities. Only someone
with the locator can read that session through the coordinator. Locators are
reusable until expiry; they are not production identity or tenant authorization.
Private engine/gateway/tunnel tokens stay server-side. A Workers VPC service binds
only the coordinator's loopback port; the origin has no public HTTP route or DNS
record. Tunnel traffic is encrypted, with a private HTTP hop on the same VPS.
The Worker permits only four fixed
operations and checks request origins and body size. Its 240 requests/minute/IP
limit is location-local, not a global abuse budget; shared networks can share that
limit. The gateway enforces its own concurrency/session limits globally for this
single deployment. This is a public sandbox, not the future managed service.

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

The connector image is pinned to cloudflared 2026.9.3. VPC requires QUIC transport
and outbound UDP port 7844. It is a Cloudflare beta integration; monitor changes
and preserve the self-hosted HTTP contract. See the [official VPC setup guide](https://developers.cloudflare.com/workers-vpc/get-started/)
and [tunnel requirements](https://developers.cloudflare.com/workers-vpc/configuration/tunnel/).

Coordinator/proxy tests: `cd site && npm test`. They cover credentials, route and
body limits, exact write/read integrity, rejected indices, batch failure without
acknowledgement advancement and retry. Verify the deployed page at desktop and
mobile sizes, cache/durable modes, context clearing, pause/resume, exact reads,
cross-tab recall and visible failure states before publishing.

## Website design references

Reviewed before implementing this demo: [Upstash Redis](https://upstash.com/redis)
for setup and latency emphasis; [Turso](https://turso.tech) for code-first onboarding
and per-agent architecture; [Valkey](https://valkey.io) for clear access to docs,
downloads and a runnable service. The later website redesign also reviewed
[Redis](https://redis.io/) and Valkey for clear product and installation paths.
instantKV now uses a minimal white layout, neutral type and diagrams that expand
when needed. Its homepage leads with local memory, runnable examples and measured
results. Native phone integrations and device performance goals are marked as
planned work.
