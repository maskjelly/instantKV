import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { createGateway } from "./gateway.mjs";
import { eventBase } from "./fixtures.mjs";

async function fixture(t, native = false) {
  const records = new Map();
  const calls = [];
  let fail = () => false;
  let oversized = false;
  const fetcher = async (url, request) => {
    assert.equal(request.headers.authorization, "Bearer private-backend-token");
    calls.push({ url, ...request });
    if (fail(url)) return Response.json({}, { status: 503 });
    const route = new URL(url);
    const root = "/v1/namespaces/demo_memories/memories";
    assert(route.pathname.startsWith(root));
    if (request.method === "POST") {
      const input = JSON.parse(request.body);
      const path = root + "/" + input.key;
      if (records.has(path)) return Response.json({}, { status: 409 });
      const hit = {
        key: input.key,
        revision: 7,
        written_at_ms: 123,
        expires_at_ms: 900123,
        memory: { _instantkv_memory: 1, ...input.memory },
      };
      records.set(path, hit);
      return Response.json(hit);
    }
    if (request.method === "DELETE") {
      assert.equal(request.headers["if-match"], '"7"');
      records.delete(route.pathname);
      return new Response(null, { status: 204 });
    }
    if (route.pathname === root) {
      const p = route.searchParams;
      const items = [...records.values()]
        .filter((h) => h.memory.tags.includes(p.get("tag")))
        .filter((h) => !p.has("topic") || h.memory.topic === p.get("topic"))
        .filter(
          (h) => !p.has("query") || h.memory.content.includes(p.get("query")),
        )
        .filter(
          (h) =>
            !p.has("since_ms") ||
            h.memory.occurred_at_ms >= Number(p.get("since_ms")),
        )
        .sort((a, b) => b.memory.occurred_at_ms - a.memory.occurred_at_ms)
        .slice(0, 10);
      return Response.json({
        items,
        next_cursor: null,
        scanned: items.length,
        scanned_bytes: 1000,
      });
    }
    if (oversized) return new Response("x".repeat(65537));
    return Response.json(records.get(route.pathname) || {}, {
      status: records.has(route.pathname) ? 200 : 404,
    });
  };
  let backend;
  if (native) {
    backend = http.createServer(async (req, res) => {
      let body = "";
      for await (const chunk of req) body += chunk;
      const response = await fetcher("http://engine" + req.url, {
        method: req.method,
        headers: req.headers,
        body,
      });
      res.writeHead(response.status, Object.fromEntries(response.headers));
      res.end(await response.text());
    });
    await new Promise((done) => backend.listen(0, "127.0.0.1", done));
    t.after(() => {
      backend.close();
      backend.closeAllConnections();
    });
  }
  const server = createGateway({
    backend: native
      ? "http://127.0.0.1:" + backend.address().port
      : "http://engine",
    backendToken: "private-backend-token",
    gatewayToken: "private-gateway-token",
    fetcher: native ? undefined : fetcher,
  });
  await new Promise((done) => server.listen(0, "127.0.0.1", done));
  t.after(() => {
    server.close();
    server.closeAllConnections();
  });
  const call = async (path, data, token = "private-gateway-token") => {
    const response = await fetch(
      "http://127.0.0.1:" + server.address().port + path,
      {
        method: "POST",
        headers: {
          authorization: "Bearer " + token,
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
    calls,
    setFailure: (f) => {
      fail = f;
    },
    oversize: () => {
      oversized = true;
    },
  };
}
const settings = {
  count: 513,
  valueBytes: 512,
  content: "Keep source references.",
};
test("remember, filtered recall, browse and revision-checked forget use the memory API", async (t) => {
  const { call, records, calls } = await fixture(t);
  const {
    value: { id },
  } = await call("/session", settings);
  assert.match(id, /^[a-f0-9]{48}$/);
  assert.equal((await call("/read", { id, index: 0 })).status, 400);
  const first = await call("/write", { id, offset: 0 });
  assert.equal(first.value.written, 512);
  assert.equal(first.value.operation_ms.length, 512);
  await call("/write", { id, offset: 512 });
  assert.equal(records.size, 513);
  const read = await call("/read", { id, index: 512 });
  assert.equal(read.value.memory.metadata.record_id, 512);
  assert.equal(read.value.verified, true);
  const recall = await call("/query", {
    id,
    topic: "preferences",
    tag: "local",
    query: "references",
    since_ms: eventBase + 500 * 60000,
  });
  assert(recall.value.items.length > 0);
  assert(
    recall.value.items.every(
      (h) =>
        h.memory.topic === "preferences" && h.memory.metadata.record_id >= 500,
    ),
  );
  assert.equal((await call("/forget", { id, index: 512 })).value.deleted, true);
  assert.equal((await call("/read", { id, index: 512 })).status, 410);
  assert(
    !(await call("/query", { id })).value.items.some(
      (h) => h.memory.metadata.record_id === 512,
    ),
  );
  assert.equal((await call("/status", { id })).value.written, 513);
  assert(calls.every((c) => !c.url.includes("/records/")));
});
test("authorization, request bounds, filters and session isolation fail closed", async (t) => {
  const { call, records } = await fixture(t);
  assert.equal((await call("/session", settings, "wrong")).status, 401);
  assert.equal(
    (await call("/session", { ...settings, content: "x".repeat(9000) })).status,
    413,
  );
  assert.equal(
    (await call("/session", { ...settings, count: 10001 })).status,
    400,
  );
  const {
    value: { id },
  } = await call("/session", { ...settings, count: 4 });
  const other = (await call("/session", { ...settings, count: 4 })).value.id;
  await call("/write", { id, offset: 0 });
  await call("/write", { id: other, offset: 0 });
  const page = (await call("/query", { id })).value;
  assert.equal(page.items.length, 4);
  assert(page.items.every((h) => h.key.startsWith("run/" + id + "/")));
  for (const filters of [
    { topic: "unknown" },
    { tag: "run-" + other },
    { query: 7 },
    { since_ms: -1 },
    { since_ms: 10, until_ms: 1 },
    { cursor: "x".repeat(4097) },
  ])
    assert.equal((await call("/query", { id, ...filters })).status, 400);
  assert.equal((await call("/forget", { id, index: 4 })).status, 400);
  assert.equal((await call("/read", { id: "guessed", index: 0 })).status, 410);
  assert.equal(records.size, 8);
});
test("partial retries preserve existing revisions and reject conflicting stored values", async (t) => {
  const { call, setFailure, records } = await fixture(t);
  const {
    value: { id },
  } = await call("/session", { ...settings, count: 8 });
  setFailure((url) => url.includes("/memories") && records.size === 5);
  assert.equal((await call("/write", { id, offset: 0 })).status, 503);
  assert.equal((await call("/status", { id })).value.written, 0);
  setFailure(() => false);
  const path = [...records.keys()][0];
  const original = structuredClone(records.get(path));
  records.get(path).memory.content = "conflict";
  assert.equal((await call("/write", { id, offset: 0 })).status, 503);
  assert.equal((await call("/status", { id })).value.written, 0);
  records.set(path, original);
  assert.equal((await call("/write", { id, offset: 0 })).value.written, 8);
  assert.deepEqual(records.get(path), original);
});
test("native keep-alive transport supports memory JSON and bounds responses", async (t) => {
  const { call, oversize } = await fixture(t, true);
  const {
    value: { id },
  } = await call("/session", { ...settings, count: 4 });
  assert.equal((await call("/write", { id, offset: 0 })).value.written, 4);
  assert.equal((await call("/read", { id, index: 3 })).value.verified, true);
  assert.equal((await call("/forget", { id, index: 2 })).value.deleted, true);
  oversize();
  assert.equal((await call("/read", { id, index: 3 })).status, 503);
});
