import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildReplay, validateRecording } from "./replay-data.mjs";
const directory = new URL(
  "../../docs/demo-results/2026-10-03-memory/",
  import.meta.url,
).pathname;
const raw = (i) =>
  JSON.parse(readFileSync(directory + "/memory-" + i + ".json", "utf8"));
test("recorded mode preserves the median real memory run, tool responses and measured timings", () => {
  const r = buildReplay(directory).recording;
  const expected = [raw(1), raw(2), raw(3)].sort(
    (a, b) => a.records_per_second - b.records_per_second,
  )[1];
  assert.equal(r.iteration, expected.iteration);
  assert.equal(r.records_per_second, expected.records_per_second);
  assert.deepEqual(r.queries, expected.queries);
  assert.deepEqual(r.forgotten, expected.forgotten);
  assert.equal(r.batches[0].operation_ms, undefined);
});
test("recordings reject altered timing, acknowledgements, memory fields and filter results", () => {
  for (const change of [
    (r) => {
      r.records_per_second *= 2;
    },
    (r) => {
      r.latency_ms.p50 /= 2;
    },
    (r) => {
      r.batches[0].written--;
    },
    (r) => {
      r.reads[0].memory.content = "invented";
    },
    (r) => {
      r.queries[1].value.items[0].memory.topic = "wrong";
    },
    (r) => {
      r.forgotten.absent.value.items = [r.reads[0]];
    },
  ]) {
    const r = raw(1);
    change(r);
    assert.throws(() => validateRecording(r));
  }
});
