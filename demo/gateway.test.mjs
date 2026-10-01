import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { createGateway } from "./gateway.mjs";

async function fixture(t, options = {}) {
  const records = new Map();
  let fail = false;
  const server = createGateway({
    backend: "http://engine",
    backendToken: "private-backend-token",
    gatewayToken: "private-gateway-token",
    fetcher: async (url, request) => {
      assert.equal(
        request.headers.authorization,
        "Bearer private-backend-token",
      );
      if (typeof fail === "function" ? fail(url) : fail)
        return new Response("{}", { status: 503 });
      const path = new URL(url).pathname;
      if (request.method === "PUT") {
        records.set(path, request.body);
        return Response.json({ revision: 1 });
      }
      return new Response(records.get(path), {
        status: records.has(path) ? 200 : 404,
        headers: { etag: '"1"' },
      });
    },
    ...options,
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(
    () =>
      new Promise((resolve) => {
        server.close(resolve);
        server.closeAllConnections();
      }),
  );
  const call = async (path, data, token = "private-gateway-token") => {
    const response = await fetch(
      `http://127.0.0.1:${server.address().port}${path}`,
      {
        method: "POST",
        headers: {
          authorization: `Bearer ${token}`,
          "content-type": "application/json",
        },
        body: JSON.stringify(data),
      },
    );
    return { status: response.status, value: await response.json() };
  };
  return {
    call,
    records,
    setFailure: (value) => {
      fail = value;
    },
  };
}
const settings = {
  mode: "cache",
  count: 513,
  valueBytes: 512,
  content: "Keep source references.",
};

test("acknowledged batches contain actual backend writes; independent reads verify exact values", async (t) => {
  const { call, records } = await fixture(t);
  const session = await call("/session", settings);
  assert.equal(session.status, 201);
  assert.match(session.value.id, /^[a-f0-9]{48}$/);
  const id = session.value.id;
  assert.equal((await call("/read", { id, index: 0 })).status, 400);
  const first = await call("/write", { id, offset: 0 });
  assert.equal(first.value.written, 512);
  assert.equal(first.value.operation_ms.length, 512);
  assert.equal(records.size, 512);
  assert(first.value.p50_ms <= first.value.p95_ms);
  assert(first.value.p95_ms <= first.value.p99_ms);
  const second = await call("/write", { id, offset: 512 });
  assert.equal(second.value.written, 513);
  assert.equal(records.size, 513);
  const read = await call("/read", { id, index: 512 });
  assert.equal(read.value.verified, true);
  assert.equal(read.value.value.record_id, 512);
  assert(read.value.value.content.startsWith(settings.content));
  assert.equal((await call("/status", { id })).value.written, 513);
  assert.equal((await call("/write", { id, offset: 513 })).status, 409);
});

test("private authorization, body limits, bounds and session capabilities fail closed", async (t) => {
  const { call, records } = await fixture(t);
  assert.equal((await call("/session", settings, "wrong")).status, 401);
  assert.equal(
    (await call("/session", { ...settings, content: "x".repeat(9000) })).status,
    413,
  );
  assert.equal(
    (await call("/session", { ...settings, count: 100001 })).status,
    400,
  );
  assert.equal(
    (await call("/session", { ...settings, mode: "durable", count: 10001 }))
      .status,
    400,
  );
  assert.equal(
    (await call("/session", { ...settings, content: null })).status,
    400,
  );
  const {
    value: { id },
  } = await call("/session", settings);
  assert.equal((await call("/write", { id, offset: -1 })).status, 409);
  assert.equal((await call("/read", { id, index: -1 })).status, 400);
  assert.equal((await call("/read", { id: "guessed", index: 0 })).status, 410);
  assert.equal(records.size, 0);
});

test("failed batch does not advance acknowledgement; same offset can be retried", async (t) => {
  const { call, setFailure, records } = await fixture(t);
  const {
    value: { id },
  } = await call("/session", { ...settings, count: 8, mode: "durable" });
  setFailure((url) => url.includes("memory/000005"));
  assert.equal((await call("/write", { id, offset: 0 })).status, 503);
  assert.equal((await call("/status", { id })).value.written, 0);
  assert.equal(records.size, 7);
  setFailure(false);
  assert.equal((await call("/write", { id, offset: 0 })).value.written, 8);
  assert.equal(
    (await call("/read", { id, index: 7 })).value.namespace,
    "demo_knowledge",
  );
});

test("native keep-alive transport preserves backend values and bounds response size", async (t) => {
  const values = new Map();
  let oversized = false;
  const backend = http.createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) body += chunk;
    const path = new URL(req.url, "http://localhost").pathname;
    res.setHeader("content-type", "application/json");
    res.setHeader("etag", '"7"');
    if (req.method === "PUT") {
      values.set(path, body);
      res.end('{"revision":7}');
    } else res.end(oversized ? "x".repeat(8193) : values.get(path));
  });
  await new Promise((resolve) => backend.listen(0, "127.0.0.1", resolve));
  t.after(
    () =>
      new Promise((resolve) => {
        backend.close(resolve);
        backend.closeAllConnections();
      }),
  );
  const { call } = await fixture(t, {
    backend: `http://127.0.0.1:${backend.address().port}`,
    fetcher: undefined,
  });
  const {
    value: { id },
  } = await call("/session", { ...settings, count: 4 });
  assert.equal((await call("/write", { id, offset: 0 })).value.written, 4);
  assert.equal((await call("/read", { id, index: 3 })).value.verified, true);
  oversized = true;
  assert.equal((await call("/read", { id, index: 3 })).status, 503);
});
