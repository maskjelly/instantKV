import http from "node:http";
import { isDeepStrictEqual } from "node:util";
import {
  topics,
  namespace,
  memoryKey,
  sessionTag,
  memoryInput,
  expectedMemory,
} from "./fixtures.mjs";
import { randomBytes, timingSafeEqual } from "node:crypto";
import { pathToFileURL } from "node:url";

// This coordinator generates synthetic fixtures. Every record is written/read
// through the unchanged Rust HTTP API; the coordinator never caches values.
export function createGateway({
  backend,
  backendToken,
  gatewayToken,
  fetcher,
}) {
  if (!backendToken || !gatewayToken)
    throw new Error("Private credentials required");
  const agent = new http.Agent({
    keepAlive: true,
    maxSockets: 32,
    maxFreeSockets: 16,
  });
  const requestBackend =
    fetcher ||
    ((url, options) =>
      new Promise((resolve, reject) => {
        const upstream = http.request(
          url,
          { agent, method: options.method || "GET", headers: options.headers },
          (response) => {
            const chunks = [];
            let bytes = 0;
            response.on("data", (chunk) => {
              bytes += chunk.length;
              if (bytes > 65536) {
                response.destroy(
                  new Error("Backend response exceeds demo limit"),
                );
                return;
              }
              chunks.push(chunk);
            });
            response.on("error", reject);
            response.on("end", () => {
              const data = Buffer.concat(chunks).toString("utf8");
              const status = response.statusCode || 502;
              resolve({
                ok: status >= 200 && status < 300,
                status,
                headers: {
                  get: (name) => response.headers[name.toLowerCase()] || null,
                },
                json: async () => JSON.parse(data),
              });
            });
          },
        );
        upstream.on("error", reject);
        upstream.setTimeout(10000, () =>
          upstream.destroy(new Error("Backend deadline exceeded")),
        );
        upstream.end(options.body);
      }));
  const sessions = new Map();
  let activeBatches = 0;
  const ttl = 900;
  const headers = {
    authorization: `Bearer ${backendToken}`,
    "content-type": "application/json",
  };
  const key = memoryKey;
  const record = memoryInput;
  const root = "/v1/namespaces/" + namespace + "/memories";
  const raw = (path, options = {}) =>
    requestBackend(backend + path, {
      ...options,
      headers: { ...headers, ...options.headers },
      redirect: "error",
    });
  const matches = (session, index, hit) =>
    hit.key === key(session, index) &&
    isDeepStrictEqual(hit.memory, expectedMemory(session, index));
  async function call(path, options = {}) {
    const response = await raw(path, options);
    if (!response.ok) {
      await response.body?.cancel();
      const error = new Error(
        response.status === 404
          ? "Memory was deleted or expired. Start a new run."
          : "Storage request failed. Retry this batch.",
      );
      error.status =
        response.status === 404 ? 410 : response.status === 400 ? 400 : 503;
      throw error;
    }
    return response;
  }
  const round = (n) => Math.round(n * 1000) / 1000;
  const send = (res, status, data) => {
    res.writeHead(status, {
      "content-type": "application/json",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    });
    res.end(JSON.stringify(data));
  };
  const server = http.createServer(async (req, res) => {
    try {
      const supplied = Buffer.from(req.headers.authorization || "");
      const expected = Buffer.from(`Bearer ${gatewayToken}`);
      if (
        supplied.length !== expected.length ||
        !timingSafeEqual(supplied, expected)
      )
        return send(res, 401, { error: "Unauthorized" });
      if (req.method !== "POST")
        return send(res, 405, { error: "POST required" });
      let body = "";
      for await (const chunk of req) {
        body += chunk;
        if (Buffer.byteLength(body) > 8192)
          return send(res, 413, { error: "Request too large" });
      }
      let input;
      try {
        input = JSON.parse(body);
      } catch {
        return send(res, 400, { error: "Invalid JSON" });
      }
      if (!input || typeof input !== "object" || Array.isArray(input))
        return send(res, 400, { error: "Object required" });
      const path = new URL(req.url, "http://localhost").pathname;
      const now = Date.now();
      for (const [id, session] of sessions)
        if (session.expiresAt <= now && !session.busy) sessions.delete(id);
      if (path === "/session") {
        if (sessions.size >= 12)
          return send(res, 503, {
            error: "Demo is busy. Try again after a few minutes.",
          });
        const { count, valueBytes, content } = input;
        const max = 10000;
        if (
          !Number.isInteger(count) ||
          count < 1 ||
          count > max ||
          ![256, 512, 1024].includes(valueBytes) ||
          typeof content !== "string" ||
          Buffer.byteLength(content) > 256 ||
          !content.trim()
        )
          return send(res, 400, { error: "Invalid run settings" });
        const session = {
          id: randomBytes(24).toString("hex"),
          count,
          valueBytes,
          content,
          written: 0,
          bytes: 0,
          expiresAt: now + ttl * 1000,
          busy: false,
          deleted: new Set(),
        };
        sessions.set(session.id, session);
        return send(res, 201, {
          id: session.id,
          expires_at: session.expiresAt,
          batch_size: 512,
          preview: record(session, 0),
          count: session.count,
          valueBytes: session.valueBytes,
        });
      }
      const session = sessions.get(input.id);
      if (!session || session.expiresAt <= now)
        return send(res, 410, { error: "Session expired. Start a new run." });
      if (path === "/status")
        return send(res, 200, {
          id: session.id,
          count: session.count,
          written: session.written,
          bytes: session.bytes,
          deleted: [...session.deleted],
          expires_at: session.expiresAt,
        });
      if (path === "/write") {
        if (!Number.isInteger(input.offset) || input.offset !== session.written)
          return send(res, 409, {
            error: "Batch offset does not match acknowledged writes",
          });
        if (session.busy || activeBatches >= 2)
          return send(res, 429, { error: "Storage is busy. Retry shortly." });
        const count = Math.min(512, session.count - session.written);
        if (!count) return send(res, 409, { error: "Run already complete" });
        session.busy = true;
        activeBatches++;
        try {
          const started = performance.now();
          const latencies = [];
          const errors = [];
          let cursor = input.offset;
          let bytes = 0;
          await Promise.all(
            Array.from({ length: Math.min(16, count) }, async () => {
              while (cursor < input.offset + count) {
                const index = cursor++;
                const payload = JSON.stringify(record(session, index));
                const before = performance.now();
                try {
                  let response = await raw(root, {
                    method: "POST",
                    body: JSON.stringify({
                      key: key(session, index),
                      memory: record(session, index),
                      ttl_seconds: ttl,
                    }),
                  });
                  // A partial failed batch can be retried without changing earlier memories.
                  if (response.status === 409) {
                    await response.body?.cancel();
                    response = await call(root + "/" + key(session, index));
                  } else if (!response.ok) {
                    await response.body?.cancel();
                    throw new Error("Memory save failed");
                  }
                  const hit = await response.json();
                  if (!matches(session, index, hit))
                    throw new Error("Saved memory differs from fixture");
                  latencies.push(performance.now() - before);
                  bytes += Buffer.byteLength(payload);
                } catch (error) {
                  errors.push(error);
                }
              }
            }),
          );
          if (errors.length)
            return send(res, 503, {
              error:
                "Some writes failed; retry the same batch. Earlier batches remain acknowledged.",
              failed: errors.length,
            });
          const elapsed = performance.now() - started;
          session.written += count;
          session.bytes += bytes;
          latencies.sort((a, b) => a - b);
          const p = (q) =>
            round(
              latencies[
                Math.min(
                  latencies.length - 1,
                  Math.ceil(q * latencies.length) - 1,
                )
              ],
            );
          return send(res, 200, {
            written: session.written,
            total: session.count,
            batch_count: count,
            bytes: session.bytes,
            batch_ms: round(elapsed),
            records_per_second: round((count / elapsed) * 1000),
            p50_ms: p(0.5),
            p95_ms: p(0.95),
            p99_ms: p(0.99),
            operation_ms: latencies.map(round),
            errors: 0,
          });
        } finally {
          session.busy = false;
          activeBatches--;
        }
      }
      if (path === "/query") {
        const { topic, tag, query, since_ms, until_ms, cursor } = input;
        if (
          (topic !== undefined && !topics.includes(topic)) ||
          (tag !== undefined && !["local", "offline"].includes(tag)) ||
          (query !== undefined &&
            (typeof query !== "string" || Buffer.byteLength(query) > 128)) ||
          (cursor !== undefined &&
            (typeof cursor !== "string" || cursor.length > 4096)) ||
          [since_ms, until_ms].some(
            (n) => n !== undefined && (!Number.isSafeInteger(n) || n < 0),
          ) ||
          (since_ms !== undefined &&
            until_ms !== undefined &&
            since_ms > until_ms)
        )
          return send(res, 400, { error: "Invalid memory filters" });
        const params = new URLSearchParams({
          tag: sessionTag(session, tag),
          limit: "10",
          max_bytes: "16384",
        });
        for (const [name, value] of Object.entries({
          topic,
          query,
          since_ms,
          until_ms,
          cursor,
        }))
          if (value !== undefined) params.set(name, String(value));
        const started = performance.now();
        const response = await call(root + "?" + params);
        const page = await response.json();
        const verified = page.items.every((hit) => {
          const index = hit.memory.metadata.record_id;
          return (
            Number.isInteger(index) &&
            index >= 0 &&
            index < session.count &&
            matches(session, index, hit)
          );
        });
        if (!verified) throw new Error("Retrieved memory differs from fixture");
        return send(res, 200, {
          ...page,
          verified,
          backend_ms: round(performance.now() - started),
        });
      }
      if (path === "/read" || path === "/forget") {
        if (
          !Number.isInteger(input.index) ||
          input.index < 0 ||
          input.index >= session.written
        )
          return send(res, 400, {
            error: "Choose an acknowledged memory index",
          });
        if (session.deleted.has(input.index))
          return send(res, 410, { error: "Memory was deleted" });
        const started = performance.now();
        const route = root + "/" + key(session, input.index);
        const response = await call(route);
        const value = await response.json();
        if (!matches(session, input.index, value))
          throw new Error("Retrieved memory differs from fixture");
        if (path === "/forget") {
          await call(route, {
            method: "DELETE",
            headers: { "if-match": '"' + value.revision + '"' },
          });
          session.deleted.add(input.index);
          return send(res, 200, {
            key: value.key,
            deleted: true,
            backend_ms: round(performance.now() - started),
          });
        }
        return send(res, 200, {
          ...value,
          namespace,
          backend_ms: round(performance.now() - started),
          verified: true,
        });
      }
      return send(res, 404, { error: "Unknown demo operation" });
    } catch (error) {
      console.error(
        JSON.stringify({ event: "demo_failure", message: error.message }),
      );
      if (!res.headersSent)
        send(res, error.status || 503, {
          error:
            error.status === 410 || error.status === 400
              ? error.message
              : "Demo storage is temporarily unavailable",
        });
    }
  });
  server.on("close", () => agent.destroy());
  return server;
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const server = createGateway({
    backend: process.env.INSTANTKV_DEMO_BACKEND,
    backendToken: process.env.INSTANTKV_DEMO_TOKEN,
    gatewayToken: process.env.DEMO_GATEWAY_TOKEN,
  });
  server.requestTimeout = 30000;
  server.listen(8098, "0.0.0.0", () =>
    console.log("Demo coordinator ready on :8098"),
  );
}
