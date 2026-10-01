import recordedEnvironment from '../../../docs/benchmarks/2026-10-01-rove/environment.json';

const median = (values: number[]) => [...values].sort((a, b) => a - b)[1];
export interface Report {
  requests: number;
  successful_requests: number;
  errors: number;
  concurrency: number;
  successful_requests_per_second: number;
  latency_ms: { p50: number; p95: number; p99: number };
}
const reports = import.meta.glob<Report>(
  '../../../docs/benchmarks/2026-10-01-rove/*-[123].json',
  { eager: true, import: 'default' },
);
export const workloads = [
  ['scratch-get', 'Scratch GET', 'RAM · 512-byte values'],
  ['knowledge-get', 'Knowledge GET', 'Durable namespace · 512-byte values'],
  ['knowledge-put', 'Durable PUT', '512-byte updates · immediate commits'],
  ['checkpoint', 'Checkpoint save', 'Fixed capsule · no references'],
  ['restore', 'Capsule restore', 'Fixed capsule · 32 KiB response budget'],
].map(([id, name, detail]) => {
  const runs: Report[] = [1, 2, 3].map(
    (run) =>
      reports[`../../../docs/benchmarks/2026-10-01-rove/${id}-${run}.json`],
  );
  return {
    id,
    name,
    detail,
    runs,
    requests: runs[0].requests,
    concurrency: runs[0].concurrency,
    rps: median(runs.map((r) => r.successful_requests_per_second)),
    p50: median(runs.map((r) => r.latency_ms.p50)),
    p95: median(runs.map((r) => r.latency_ms.p95)),
    p99: median(runs.map((r) => r.latency_ms.p99)),
    errors: runs.reduce((sum, r) => sum + r.errors, 0),
  };
});
export const successful = workloads.reduce(
  (sum, w) => sum + w.runs.reduce((s, r) => s + r.successful_requests, 0),
  0,
);
export const errors = workloads.reduce((sum, w) => sum + w.errors, 0);
export const environment = recordedEnvironment;
