import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

export function validateRecording(report) {
  assert.equal(report.schema_version, 1);
  assert.equal(report.errors, 0);
  assert.equal(report.written, report.count);
  assert.equal(report.batches.at(-1).written, report.count);
  assert.equal(report.batches.at(-1).bytes, report.bytes);
  let written = 0;
  let elapsed = 0;
  const operations = [];
  for (const batch of report.batches) {
    assert.equal(batch.errors, 0);
    assert.equal(batch.batch_count, batch.operation_ms.length);
    assert(batch.client_ms > 0 && Number.isFinite(batch.client_ms));
    written += batch.batch_count;
    assert.equal(batch.written, written);
    elapsed += batch.client_ms;
    operations.push(...batch.operation_ms);
  }
  assert.equal(operations.length, report.count);
  assert.equal(elapsed, report.elapsed_ms);
  assert.equal(report.records_per_second, report.count / elapsed * 1000);
  operations.sort((a, b) => a - b);
  for (const [name, p] of [['p50', .5], ['p95', .95], ['p99', .99]])
    assert.equal(report.latency_ms[name], operations[Math.ceil(operations.length * p) - 1]);
  assert.equal(report.reads.length, 4);
  assert.equal(new Set(report.reads.map((sample) => sample.index)).size, 4);
  for (const sample of report.reads) {
    assert.equal(sample.verified, true);
    assert.equal(sample.value.record_id, sample.index);
    assert(sample.index >= 0 && sample.index < report.written);
    assert.equal(sample.namespace, report.mode === 'cache' ? 'demo_cache' : 'demo_knowledge');
    const expected = { ...report.preview,
      agent_id: `worker-${sample.index % 64}`, record_id: sample.index,
      kind: ['decision', 'observation', 'constraint', 'tool_result'][sample.index % 4],
      source: report.preview.source.replace(/\/0$/, `/${sample.index}`),
    };
    assert.deepEqual(sample.value, expected);
  }
  return report;
}

export function buildReplay(directory) {
  const recordings = {};
  for (const mode of ['cache', 'durable']) {
    const reports = [1, 2, 3].map((iteration) => validateRecording(JSON.parse(readFileSync(`${directory}/${mode}-${iteration}.json`, 'utf8'))));
    reports.sort((a, b) => a.records_per_second - b.records_per_second);
    const { batches, ...report } = reports[1];
    recordings[mode] = { ...report, batches: batches.map(({ operation_ms, ...batch }) => batch) };
  }
  return { schema_version: 1, playback_speed: 2, selection: 'Median throughput run of three per mode. Whole-run percentiles belong to that same run, not medians of percentiles.',
    environment: recordings.cache.environment, recordings };
}
