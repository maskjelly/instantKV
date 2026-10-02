import report from '../../../docs/benchmarks/2026-10-03-memory/mac-arm64.json';
export { report };
const median = (values: number[]) =>
  [...values].sort((a, b) => a - b)[Math.floor(values.length / 2)];
export const range = (values: number[], precision = 3) =>
  Math.min(...values).toFixed(precision) +
  '–' +
  Math.max(...values).toFixed(precision);
export const workloads = [
  {
    id: 'save',
    name: 'Remember',
    detail: 'New memory + indexes; immediate commit',
    runs: report.runs.map((r) => r.save_latency_ms),
  },
  ...(
    [
      'topic',
      'tag',
      'time',
      'combined',
      'browse',
      'keyword_first_page',
    ] as const
  ).map((id) => ({
    id,
    name: {
      topic: 'Recall by topic',
      tag: 'Recall by tag',
      time: 'Recall by event time',
      combined: 'Topic + tag + keywords',
      browse: 'Browse',
      keyword_first_page: 'Sparse keyword / first page',
    }[id],
    detail:
      id === 'keyword_first_page'
        ? '1,000 scanned candidates; no match on this page'
        : 'Up to 10 memories; 16 KiB response budget',
    runs: report.runs.map((r) => r.queries[id].latency_ms),
  })),
  {
    id: 'exact',
    name: 'Read exact key',
    detail: 'One complete memory and revision',
    runs: report.runs.map((r) => r.exact_read_latency_ms),
  },
  {
    id: 'forget',
    name: 'Forget',
    detail: 'Revision-checked delete + index removal',
    runs: report.runs.map((r) => r.forget_latency_ms),
  },
].map((w) => ({
  ...w,
  p50: median(w.runs.map((r) => r.p50)),
  p95: median(w.runs.map((r) => r.p95)),
  p99: median(w.runs.map((r) => r.p99)),
  p95Range: range(w.runs.map((r) => r.p95)),
  samples: w.runs.reduce((n, r) => n + r.samples.length, 0),
}));
export const recovered = report.runs.reduce(
  (n, r) => n + r.exact_memories_after_kill_restart,
  0,
);
export const deleted = report.runs.reduce(
  (n, r) => n + r.verified_deleted_memories,
  0,
);
export const errors = report.runs.reduce((n, r) => n + r.errors, 0);
export const largestRss = Math.max(
  ...report.runs.map((r) => r.largest_sampled_rss_bytes),
);
