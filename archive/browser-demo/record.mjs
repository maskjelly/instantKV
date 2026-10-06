// Record the real demo locally. This never changes an existing configuration.
import { createGateway } from "./gateway.mjs";
import { defaultContent, eventBase } from "./fixtures.mjs";
import { spawn, execFileSync } from "node:child_process";
import { randomBytes, createHash } from "node:crypto";
import {
  mkdtempSync,
  readFileSync,
  writeFileSync,
  mkdirSync,
  rmSync,
} from "node:fs";
import { tmpdir, cpus, totalmem, platform, release } from "node:os";
import { resolve } from "node:path";
import { once } from "node:events";

const binary = resolve(process.env.INSTANTKV_BIN || "target/release/instantkv");
const output = resolve(
  process.argv[2] || (() => { throw new Error("Provide a new output directory outside the repository."); })(),
);
if (output === resolve(".") || output.startsWith(resolve(".") + "/")) {
  throw new Error("Recordings must be written outside the repository.");
}
mkdirSync(output);
const state = mkdtempSync(`${tmpdir()}/instantkv-record-`);
const token = randomBytes(32).toString("hex");
const gatewayToken = randomBytes(32).toString("hex");
const config = readFileSync(
  new URL("./instantkv.toml", import.meta.url),
  "utf8",
)
  .replace("0.0.0.0:8080", "127.0.0.1:18089")
  .replace("/state/data", `${state}/data`);
writeFileSync(`${state}/instantkv.toml`, config, { mode: 0o600 });

const hardware =
  platform() === "darwin"
    ? {
        cpu: execFileSync("sysctl", ["-n", "machdep.cpu.brand_string"], {
          encoding: "utf8",
        }).trim(),
        physical_cores: Number(
          execFileSync("sysctl", ["-n", "hw.physicalcpu"]),
        ),
        ram_bytes: Number(execFileSync("sysctl", ["-n", "hw.memsize"])),
        macos: execFileSync("sw_vers", ["-productVersion"], {
          encoding: "utf8",
        }).trim(),
      }
    : {
        cpu: cpus()[0]?.model,
        logical_cores: cpus().length,
        ram_bytes: totalmem(),
        os: platform() + " " + release(),
      };
const environment = {
  measured_at: new Date().toISOString(),
  hardware,
  runtime_version: execFileSync(binary, ["--version"], {
    encoding: "utf8",
  }).trim(),
  runtime_source: execFileSync(
    "git",
    [
      "log",
      "-1",
      "--format=%H",
      "--",
      "crates/instantkv-core/src",
      "crates/instantkv/src",
    ],
    { encoding: "utf8" },
  ).trim(),
  source_dirty: !!execFileSync("git", ["status", "--porcelain"], {
    encoding: "utf8",
  }).trim(),
  recorder_source: execFileSync("git", ["rev-parse", "HEAD"], {
    encoding: "utf8",
  }).trim(),
  recorder_files_sha256: Object.fromEntries(
    ["record.mjs", "gateway.mjs", "fixtures.mjs", "instantkv.toml"].map(
      (name) => [
        name,
        createHash("sha256")
          .update(readFileSync(new URL("./" + name, import.meta.url)))
          .digest("hex"),
      ],
    ),
  ),
  binary_sha256: createHash("sha256")
    .update(readFileSync(binary))
    .digest("hex"),
  transport:
    "Loopback HTTP/1.1; coordinator-to-Rust keep-alive; no Cloudflare or public network",
  concurrency: 16,
  batch_size: 512,
  context_characters: 512,
  cpu_container_limit: null,
  ttl_seconds: 900,
  runs: 3,
  notes:
    "Current structured-memory API. One fresh dedicated database; three durable sessions in sequence. No warmup, pauses or session creation in write timing. Other Mac applications remained running. Content is 512 ASCII bytes plus metadata/envelope. Payload excludes keys and storage overhead. Each query/read response is preserved; one revision-checked forget and index absence check follow queries. Synthetic fixtures, no model inference.",
};
const backend = spawn(
  binary,
  ["serve", "--config", `${state}/instantkv.toml`],
  {
    env: { ...process.env, INSTANTKV_DEMO_TOKEN: token },
    stdio: "ignore",
  },
);
let gateway;
try {
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    if (backend.exitCode !== null)
      throw new Error("Rust server exited; check that port 18089 is free");
    try {
      ready = (await fetch("http://127.0.0.1:18089/healthz")).ok;
    } catch {}
    if (ready) break;
    await new Promise((done) => setTimeout(done, 100));
  }
  if (!ready) throw new Error("Rust server did not become ready");
  gateway = createGateway({
    backend: "http://127.0.0.1:18089",
    backendToken: token,
    gatewayToken,
  });
  gateway.listen(0, "127.0.0.1");
  await once(gateway, "listening");
  const address = `http://127.0.0.1:${gateway.address().port}`;
  async function call(operation, input) {
    const started = performance.now();
    const response = await fetch(`${address}/${operation}`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${gatewayToken}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(input),
      signal: AbortSignal.timeout(30000),
    });
    const value = await response.json();
    if (!response.ok)
      throw new Error(`${operation}: ${response.status} ${value.error}`);
    return { value, client_ms: performance.now() - started };
  }
  for (let iteration = 1; iteration <= 3; iteration++) {
    const count = 10000;
    const content = defaultContent;
    const { value: session } = await call("session", {
      count,
      valueBytes: 512,
      content,
    });
    let written = 0;
    const batches = [];
    const operations = [];
    while (written < count) {
      const { value, client_ms } = await call("write", {
        id: session.id,
        offset: written,
      });
      written = value.written;
      operations.push(...value.operation_ms);
      batches.push({ ...value, client_ms });
    }
    const reads = [];
    for (const index of [
      0,
      Math.floor(count / 4),
      Math.floor(count / 2),
      count - 1,
    ]) {
      const { value, client_ms } = await call("read", {
        id: session.id,
        index,
      });
      if (!value.verified || value.memory.metadata.record_id !== index)
        throw new Error("Exact read verification failed");
      reads.push({ index, ...value, client_ms });
    }
    const queries = [];
    const presets = [
      ["browse", {}],
      ["topic", { topic: "preferences" }],
      ["tag", { tag: "local" }],
      [
        "time",
        {
          since_ms: eventBase + (count - 20) * 60000,
          until_ms: eventBase + (count - 1) * 60000,
        },
      ],
      ["keyword", { query: "Rust local" }],
      ["combined", { topic: "preferences", tag: "local", query: "Rust" }],
    ];
    for (const [name, input] of presets) {
      const { value, client_ms } = await call("query", {
        id: session.id,
        ...input,
      });
      if (!value.verified || !value.items.length)
        throw new Error("Query verification failed");
      queries.push({ name, input, value, client_ms });
    }
    const second = await call("query", {
      id: session.id,
      cursor: queries[0].value.next_cursor,
    });
    queries.push({
      name: "browse_next",
      input: { cursor: queries[0].value.next_cursor },
      ...second,
    });
    const forgotten = await call("forget", {
      id: session.id,
      index: count - 1,
    });
    const absent = await call("query", {
      id: session.id,
      since_ms: eventBase + (count - 1) * 60000,
      until_ms: eventBase + (count - 1) * 60000,
    });
    if (absent.value.items.length)
      throw new Error("Deleted memory remains in index");
    operations.sort((a, b) => a - b);
    const elapsed = batches.reduce((sum, batch) => sum + batch.client_ms, 0);
    const percentile = (p) => operations[Math.ceil(operations.length * p) - 1];
    const report = {
      schema_version: 2,
      environment,
      iteration,
      count,
      content,
      session_id: session.id,
      preview: session.preview,
      errors: 0,
      written,
      bytes: batches.at(-1).bytes,
      elapsed_ms: elapsed,
      records_per_second: (count / elapsed) * 1000,
      latency_ms: {
        p50: percentile(0.5),
        p95: percentile(0.95),
        p99: percentile(0.99),
      },
      batches,
      reads,
      queries,
      forgotten: { index: count - 1, ...forgotten, absent },
    };
    writeFileSync(`${output}/memory-${iteration}.json`, JSON.stringify(report));
    console.log(
      JSON.stringify({
        iteration,
        records: written,
        records_per_second: Math.round(report.records_per_second),
        latency_ms: report.latency_ms,
        verified_reads: reads.length,
        errors: 0,
      }),
    );
  }
  writeFileSync(
    `${output}/environment.json`,
    JSON.stringify(environment, null, 2) + "\n",
  );
} finally {
  if (gateway) await new Promise((done) => gateway.close(done));
  backend.kill("SIGTERM");
  if (backend.exitCode === null) await once(backend, "exit");
  rmSync(state, { recursive: true, force: true });
}
