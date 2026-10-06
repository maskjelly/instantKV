import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { expectedMemory, memoryKey, sessionTag } from "./fixtures.mjs";
const close = (a, b) =>
  assert(Math.abs(a - b) < 0.000001, "Measured values must stay unchanged");
export function validateRecording(r) {
  assert.equal(r.schema_version, 2);
  assert.equal(r.errors, 0);
  assert.equal(r.written, r.count);
  assert.equal(r.count, 10000);
  assert.match(r.environment.runtime_source, /^[a-f0-9]{40}$/);
  assert.match(r.environment.binary_sha256, /^[a-f0-9]{64}$/);
  const samples = r.batches
    .flatMap((b) => b.operation_ms)
    .sort((a, b) => a - b);
  assert.equal(samples.length, r.count);
  let written = 0;
  for (const batch of r.batches) {
    assert.equal(batch.errors, 0);
    written += batch.batch_count;
    assert.equal(batch.written, written);
    assert.equal(batch.operation_ms.length, batch.batch_count);
    assert(batch.client_ms > 0);
  }
  close(
    r.elapsed_ms,
    r.batches.reduce((sum, b) => sum + b.client_ms, 0),
  );
  close(r.records_per_second, (r.count / r.elapsed_ms) * 1000);
  for (const p of [50, 95, 99])
    close(
      r.latency_ms["p" + p],
      samples[Math.ceil((samples.length * p) / 100) - 1],
    );
  const session = {
    id: r.session_id,
    content: r.content,
    valueBytes: r.environment.context_characters,
  };
  assert.deepEqual(
    r.preview,
    (({ _instantkv_memory, ...input }) => input)(expectedMemory(session, 0)),
  );
  const checkHit = (hit) => {
    const index = hit.memory.metadata.record_id;
    assert(Number.isInteger(index) && index >= 0 && index < r.count);
    assert.equal(hit.key, memoryKey(session, index));
    assert.deepEqual(hit.memory, expectedMemory(session, index));
    assert(Number.isInteger(hit.revision) && hit.revision > 0);
    assert(hit.written_at_ms > 0 && hit.expires_at_ms > hit.written_at_ms);
  };
  assert.equal(r.reads.length, 4);
  assert.equal(new Set(r.reads.map((read) => read.index)).size, 4);
  r.reads.forEach((read) => {
    assert.equal(read.verified, true);
    checkHit(read);
    assert.equal(read.index, read.memory.metadata.record_id);
  });
  assert.deepEqual(
    r.queries.map((q) => q.name),
    ["browse", "topic", "tag", "time", "keyword", "combined", "browse_next"],
  );
  for (const q of r.queries) {
    assert.equal(q.value.verified, true);
    assert(q.value.items.length > 0 && q.value.items.length <= 10);
    assert(q.value.scanned <= 1000);
    q.value.items.forEach((hit) => {
      checkHit(hit);
      if (q.input.topic) assert.equal(hit.memory.topic, q.input.topic);
      assert(hit.memory.tags.includes(sessionTag(session, q.input.tag)));
      if (q.input.since_ms)
        assert(hit.memory.occurred_at_ms >= q.input.since_ms);
      if (q.input.until_ms)
        assert(hit.memory.occurred_at_ms <= q.input.until_ms);
      if (q.input.query)
        for (const term of q.input.query.toLowerCase().split(/\s+/))
          assert(hit.memory.content.toLowerCase().includes(term));
    });
    const times = q.value.items.map((h) => h.memory.occurred_at_ms);
    assert.deepEqual(
      times,
      [...times].sort((a, b) => b - a),
    );
  }
  assert.equal(r.queries[6].input.cursor, r.queries[0].value.next_cursor);
  const keys = new Set(r.queries[0].value.items.map((h) => h.key));
  assert(r.queries[6].value.items.every((h) => !keys.has(h.key)));
  assert.equal(r.forgotten.value.deleted, true);
  assert.equal(r.forgotten.value.key, memoryKey(session, r.forgotten.index));
  assert.deepEqual(r.forgotten.absent.value.items, []);
  return r;
}
export function buildReplay(directory) {
  const reports = [1, 2, 3].map((i) =>
    validateRecording(
      JSON.parse(readFileSync(directory + "/memory-" + i + ".json", "utf8")),
    ),
  );
  const selected = [...reports].sort(
    (a, b) => a.records_per_second - b.records_per_second,
  )[1];
  const { batches, ...recording } = selected;
  return {
    schema_version: 2,
    selection:
      "Median throughput of three current structured-memory runs; saved responses, no new storage requests.",
    recording: {
      ...recording,
      batches: batches.map(({ operation_ms, ...batch }) => batch),
    },
  };
}
