# Live memory demo

[Open the live demo](https://instantkv.com/demo/). No account or model API key is
needed. Choose RAM cache or durable storage, edit the synthetic context and start
the writer. The page displays only acknowledged writes. Clear local context,
choose a record index and recall it from the separate reader. **Open reader in
new tab** carries only a session locator; the new page fetches the value from the
Rust service rather than receiving a copy of the writer's context.

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

Cloudflare hosts the public site and request proxy. Rust/redb runs on a VPS with
persistent storage. Cloudflare KV, browser storage and simulated timers are not
used as substitutes for instantKV. The small Node coordinator is demo workload
generation and batching, not a second storage engine.

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
| Exact verification | Fetched JSON equals the deterministic fixture for the requested record |
| Failed requests | Rejected browser API responses; failed batch replies also include their backend failure count |

Context length is a character count for the content field; the complete JSON
record is larger. Agent IDs cycle across 64 synthetic workers. The shared demo
does not model namespace isolation between those synthetic workers. The actual
scoped-worker isolation and checkpoint/restart demonstration is
[the CLI swarm demo](demo.md). Use the [controlled benchmark page](benchmarks.md)
for the separate three-run, hardware-recorded measurements; public demo timings
vary with geography, shared-host load and concurrent visitors.

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
downloads and a runnable service. instantKV retains its original graphite/chrome
identity. Its homepage and navigation now lead directly to working storage and
evidence, with no signup flow or copied product artwork.
