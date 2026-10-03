# Live memory demo

**Historical guide.** The public website demo is retired. Use [quick start](quickstart.md) to run the memory service locally.


[Read local setup](quickstart.md). No account or model key is needed.
Live mode calls the current structured-memory API on our Rust service.
Recorded mode shows saved responses from fresh Mac runs.

## Try the memory lifecycle

1. Select **Live memory API**. Remember 100 synthetic memories.
2. Clear local context. The session locator stays in the URL; saved values do not.
3. Recall by topic, tag, event time or literal keywords.
4. Browse all memories, then open the next page.
5. Select a result or read an exact index. Press **Forget**.
6. Read the same index again. The server reports that it was deleted.

The independent reader link opens a new tab with only a random session locator.
It fetches values from Rust storage. No model inference or automatic memory extraction runs.

Fixtures contain content, four topics, session-scoped local/offline tags,
one-minute event times and custom JSON metadata.
The event clock starts at 2026-10-03 00:00 UTC. It is synthetic, separate from save/expiry time.
Date inputs use your browser's local timezone. Responses show UTC event times.

Queries return at most 10 memories in 16 KiB.
A cursor continues the same filters. An empty bounded page can still have a next cursor.
Keyword filtering matches literal content; it is not semantic search.

## Actual storage path

```text
Browser writer / independent reader
  → same-origin HTTPS /api/demo/*
  → Cloudflare Worker: origin check, body cap, per-IP rate limit
  → private VPC binding and QUIC tunnel
  → isolated Node coordinator: synthetic fixtures and session bounds
  → Rust /memories API
  → redb: memory + topic/tag/time indexes in one transaction
```

The coordinator makes real remember, query, exact-read and forget requests.
It does not cache saved values. It retains fixture inputs to verify returned fields.
Queries always include a session-specific tag. Filters cannot expose another run.
Forget reads the current revision, then deletes with `If-Match`.
Partial failed batches retry existing keys only after verifying their exact memory fields.

The website is hosted; the memory engine itself needs no cloud service.

## Recorded responses and timing

Recorded mode (retired) loads the median-throughput
run from three new 10,000-memory sessions on an Apple M4 Pro with 24 GiB RAM.
All 30,000 saves were acknowledged; four exact reads per run matched every fixture field.
Each run saved six query types, browse continuation and a verified deletion.
[Raw reports and conditions](demo-results/2026-10-03-memory/README.md).

Recorded controls choose queries that actually ran. The page shows original backend timings.
There is no new storage request or timed browser recall in this mode.
Clearing displayed context does not remove the cached recording.
Recorded deletion receipts remain in the downloaded data. Use live mode to delete a memory.

| Timing | What it includes |
| --- | --- |
| Backend | Coordinator-to-Rust HTTP request, response and JSON parsing |
| Live browser | Worker, tunnel, network and coordinator round-trip |
| Save p50 / p99 | Actual per-memory backend latencies; 16 concurrent saves |

Writes use batches of at most 512 memories. Only complete successful batches advance the count.
The [sequential local benchmark](performance.md) uses concurrency one and fresh databases.
Its numbers are separate from this demo's queued writes and public-network timing.

## Bounds and deployment

Use synthetic data. Records and session locators expire after 15 minutes.
The gateway permits at most 12 sessions, two simultaneous batches and 16 concurrent backend requests per batch.
Each session permits at most 10,000 memories with 512-character content in the UI.
The `demo_memories` namespace has a 128 MiB logical quota and a 120,000-entry limit.
Full durable storage rejects writes. Query budgets and the 8 MiB redb cache are separate from total RSS.

The Rust container has a 512 MiB/one-CPU limit. The coordinator has a 192 MiB/half-CPU limit.
The Worker allows only session, write, read, status, query and forget operations.
Its 240-requests/minute/IP limit applies per location.

A random 192-bit locator permits querying and deleting that run until expiry.
It is a demo capability, not production tenant identity.
Engine, gateway and tunnel credentials stay server-side.
Earlier namespaces remain in the config for storage compatibility; the demo principal can access only `demo_memories`.

To run the isolated backend, build the current source image first.
Copy `demo/` to a deployment directory and create a private ignored `.env` with
`INSTANTKV_DEMO_TOKEN` and `DEMO_GATEWAY_TOKEN`. Run its Compose project with a separate volume.
Keep the memory port private. The gateway binds only to host loopback port 8098.

For this website, the existing VPC binding targets that gateway through Cloudflare Tunnel.
Keep the connector token in private `.tunnel-token`. The tunnel uses QUIC.
Set the same gateway secret on the Worker, then run `npm run deploy:domain` in `site/`.
[Website deployment](website.md).

Run `cd site && npm test` for gateway, recording-integrity and proxy tests.
Before deployment, verify all four tools, combined filters, pagination, cleared context,
an independent reader, partial retry, expiry errors and mobile layout.
