// Record the real demo locally. This never changes an existing configuration.
import { createGateway } from './gateway.mjs';
import { spawn, execFileSync } from 'node:child_process';
import { randomBytes, createHash } from 'node:crypto';
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { once } from 'node:events';

const binary = resolve(process.env.INSTANTKV_BIN || 'target/release/instantkv');
const output = resolve(process.argv[2] || 'docs/demo-results/2026-10-02-mac');
const state = mkdtempSync(`${tmpdir()}/instantkv-record-`);
const token = randomBytes(32).toString('hex');
const gatewayToken = randomBytes(32).toString('hex');
const config = readFileSync(new URL('./instantkv.toml', import.meta.url), 'utf8')
  .replace('0.0.0.0:8080', '127.0.0.1:18089')
  .replace('/state/data', `${state}/data`);
writeFileSync(`${state}/instantkv.toml`, config, { mode: 0o600 });
mkdirSync(output, { recursive: true });
const hardware = {
  cpu: execFileSync('sysctl', ['-n', 'machdep.cpu.brand_string'], { encoding: 'utf8' }).trim(),
  physical_cores: Number(execFileSync('sysctl', ['-n', 'hw.physicalcpu'])),
  ram_bytes: Number(execFileSync('sysctl', ['-n', 'hw.memsize'])),
  macos: execFileSync('sw_vers', ['-productVersion'], { encoding: 'utf8' }).trim(),
};
const environment = {
  measured_at: new Date().toISOString(), hardware,
  runtime_version: execFileSync(binary, ['--version'], { encoding: 'utf8' }).trim(),
  runtime_source: '6eceb8bdd2450cc9977d0fd3c4b3627a9bf0a032',
  recorder_source: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  binary_sha256: createHash('sha256').update(readFileSync(binary)).digest('hex'),
  transport: 'Loopback HTTP/1.1; coordinator-to-Rust keep-alive; no Cloudflare or public network',
  concurrency: 16, batch_size: 512, context_characters: 512,
  cpu_container_limit: null, ttl_seconds: 900, runs_per_mode: 3,
  notes: 'One fresh dedicated database; six sessions in sequence, reads immediately after each run. No warmup, pauses or session creation in write timing. Other Mac applications remained running. Payload excludes keys and storage overhead. RAM FIFO may evict older sessions. Samples preserve real GET responses; these are synthetic agent fixtures, not model quality tests.',
};
const backend = spawn(binary, ['serve', '--config', `${state}/instantkv.toml`], {
  env: { ...process.env, INSTANTKV_DEMO_TOKEN: token }, stdio: 'ignore',
});
let gateway;
try {
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    if (backend.exitCode !== null) throw new Error('Rust server exited; check that port 18089 is free');
    try { ready = (await fetch('http://127.0.0.1:18089/healthz')).ok; } catch {}
    if (ready) break;
    await new Promise((done) => setTimeout(done, 100));
  }
  if (!ready) throw new Error('Rust server did not become ready');
  gateway = createGateway({ backend: 'http://127.0.0.1:18089', backendToken: token, gatewayToken });
  gateway.listen(0, '127.0.0.1');
  await once(gateway, 'listening');
  const address = `http://127.0.0.1:${gateway.address().port}`;
  async function call(operation, input) {
    const started = performance.now();
    const response = await fetch(`${address}/${operation}`, {
      method: 'POST', headers: { authorization: `Bearer ${gatewayToken}`, 'content-type': 'application/json' },
      body: JSON.stringify(input), signal: AbortSignal.timeout(30000),
    });
    const value = await response.json();
    if (!response.ok) throw new Error(`${operation}: ${response.status} ${value.error}`);
    return { value, client_ms: performance.now() - started };
  }
  for (const mode of ['cache', 'durable']) {
    for (let iteration = 1; iteration <= 3; iteration++) {
      const count = mode === 'cache' ? 100000 : 10000;
      const content = 'Use Rust + redb. Shared knowledge is read-only for workers. Keep source references with every decision.';
      const { value: session } = await call('session', { mode, count, valueBytes: 512, content });
      let written = 0;
      const batches = [];
      const operations = [];
      while (written < count) {
        const { value, client_ms } = await call('write', { id: session.id, offset: written });
        written = value.written;
        operations.push(...value.operation_ms);
        batches.push({ ...value, client_ms });
      }
      const reads = [];
      for (const index of [0, Math.floor(count / 4), Math.floor(count / 2), count - 1]) {
        const { value, client_ms } = await call('read', { id: session.id, index });
        if (!value.verified || value.value.record_id !== index) throw new Error('Exact read verification failed');
        reads.push({ index, ...value, client_ms });
      }
      operations.sort((a, b) => a - b);
      const elapsed = batches.reduce((sum, batch) => sum + batch.client_ms, 0);
      const percentile = (p) => operations[Math.ceil(operations.length * p) - 1];
      const report = { schema_version: 1, environment, mode, iteration, count, content,
        preview: session.preview, errors: 0, written, bytes: batches.at(-1).bytes,
        elapsed_ms: elapsed, records_per_second: count / elapsed * 1000,
        latency_ms: { p50: percentile(.5), p95: percentile(.95), p99: percentile(.99) },
        batches, reads };
      writeFileSync(`${output}/${mode}-${iteration}.json`, JSON.stringify(report));
      console.log(JSON.stringify({ mode, iteration, records: written, records_per_second: Math.round(report.records_per_second), latency_ms: report.latency_ms, verified_reads: reads.length, errors: 0 }));
    }
  }
  writeFileSync(`${output}/environment.json`, JSON.stringify(environment, null, 2) + '\n');
} finally {
  if (gateway) await new Promise((done) => gateway.close(done));
  backend.kill('SIGTERM');
  if (backend.exitCode === null) await once(backend, 'exit');
  rmSync(state, { recursive: true, force: true });
}
