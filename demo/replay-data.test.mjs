import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildReplay, validateRecording } from './replay-data.mjs';
const directory = new URL('../docs/demo-results/2026-10-02-mac/', import.meta.url).pathname;
const raw = () => JSON.parse(readFileSync(`${directory}/cache-2.json`, 'utf8'));
test('replay uses a real median run and preserves all measured performance values', () => {
  const replay = buildReplay(directory);
  assert.equal(replay.recordings.cache.iteration, 2);
  assert.equal(replay.recordings.durable.iteration, 1);
  assert.equal(replay.recordings.cache.records_per_second, raw().records_per_second);
  assert.deepEqual(replay.recordings.cache.latency_ms, raw().latency_ms);
  assert.deepEqual(replay.recordings.cache.reads, raw().reads);
  assert.equal(replay.recordings.cache.batches[0].operation_ms, undefined);
});
test('reject altered timings, missing acknowledgements and corrupted saved responses', () => {
  for (const change of [
    (r) => { r.records_per_second *= 2; },
    (r) => { r.latency_ms.p50 /= 2; },
    (r) => { r.batches[0].written--; },
    (r) => { r.reads[0].value.content = 'invented response'; },
  ]) {
    const report = raw(); change(report);
    assert.throws(() => validateRecording(report));
  }
});
