import full from '../../../docs/benchmarks/2026-10-04-full-retrieval/summary.json';
import scifact from '../../../docs/benchmarks/2026-10-04-search/scifact.json';
import arguana from '../../../docs/benchmarks/2026-10-04-search/default/arguana.json';
import nfcorpus from '../../../docs/benchmarks/2026-10-04-search/default/nfcorpus.json';
import runtime from '../../../docs/benchmarks/2026-10-04-full-retrieval/runtime-metrics.json';
export { runtime };
export { full };
export const percent = (value: number) => (100 * value).toFixed(2);
export const mib = (value: number) => (value / 1024 ** 2).toFixed(2);
export const providers = [
  'instantKV',
  'SQLite FTS5',
  'Supermemory local',
] as const;
export interface EvidenceRow {
  name: string;
  scope: string;
  count: number;
  queried: number;
  docs?: number;
  recall: (number | null)[];
  ndcg: (number | null)[];
  raw: string;
  limits: string;
}
const lme = full.suites['longmemeval-s'];
const lc = full.suites.locomo;
export const memoryEvidence: EvidenceRow[] = [
  {
    name: 'LongMemEval-S',
    scope: 'Source sessions',
    count: 500,
    queried: 500,
    recall: [lme.instantkv.recall_at_10, lme['sqlite-fts5'].recall_at_10, null],
    ndcg: [lme.instantkv.ndcg_at_10, lme['sqlite-fts5'].ndcg_at_10, null],
    raw: '/benchmark-data/full-retrieval/summary.json',
    limits: 'All 500 questions. Full local Supermemory run is incomplete.',
  },
  {
    name: 'LoCoMo',
    scope: 'Source turns',
    count: 1533,
    queried: 1986,
    recall: [
      lc.instantkv.recall_at_10,
      lc['sqlite-fts5'].recall_at_10,
      lc['supermemory-local'].recall_at_10,
    ],
    ndcg: [
      lc.instantkv.ndcg_at_10,
      lc['sqlite-fts5'].ndcg_at_10,
      lc['supermemory-local'].ndcg_at_10,
    ],
    raw: '/benchmark-data/full-retrieval/summary.json',
    limits:
      'All ten histories; 1,986 questions queried. Recall scores 1,533 positive-label questions.',
  },
];
const secondary = [
  {
    name: 'SciFact',
    report: scifact,
    native: scifact.providers.instantkv.scifact,
    control: scifact.providers.supermemory.scifact,
    raw: '/benchmark-data/search-v2/scifact.json',
    docs: 5183,
    limits: 'All 300 queries. Zero native truncations.',
  },
  {
    name: 'ArguAna',
    report: arguana,
    native: arguana.providers.instantkv,
    control: arguana.providers.supermemory,
    raw: '/benchmark-data/search-v2/default/arguana.json',
    docs: 8674,
    limits:
      '688 of 1,406 native queries truncated; 1,149 reduced. Zero rejections.',
  },
  {
    name: 'NFCorpus',
    report: nfcorpus,
    native: nfcorpus.providers.instantkv,
    control: nfcorpus.providers.supermemory,
    raw: '/benchmark-data/search-v2/default/nfcorpus.json',
    docs: 3633,
    limits: 'All 323 queries. Zero native truncations.',
  },
];
export const irEvidence: EvidenceRow[] = secondary.map((row) => ({
  name: row.name,
  scope: 'BEIR documents',
  count: row.report.test_queries,
  queried: row.report.test_queries,
  docs: row.docs,
  recall: [
    row.native.metrics.recall_at_10,
    null,
    row.control.metrics.recall_at_10,
  ],
  ndcg: [row.native.metrics.ndcg_at_10, null, row.control.metrics.ndcg_at_10],
  raw: row.raw,
  limits: row.limits,
}));

export interface RuntimeRow {
  suite: string;
  provider: string;
  recall: number;
  ndcg: number;
  latency: { p50: number; p95: number; p99: number };
  rss: number;
  failures: number;
  truncated: number;
  reduced: number;
  disk: number | null;
  diskScope: string;
  startupP95: number | null;
  writeP95: number | null;
  writeUnit: string;
  writeThroughput: number | null;
  binary: number | null;
  rssScope: string;
  samples: number;
  repetitions: number;
  raw: string;
  context: string;
}
const fullRows: RuntimeRow[] = runtime.runs.map((run) => {
  const source = memoryEvidence[run.suite === 'longmemeval-s' ? 0 : 1];
  const index = ['instantkv', 'sqlite-fts5', 'supermemory-local'].indexOf(
    run.provider,
  );
  return {
    suite: source.name,
    provider: providers[index],
    recall: source.recall[index]!,
    ndcg: source.ndcg[index]!,
    latency: run.query_latency_ms,
    rss: run.largest_sampled_rss_bytes,
    failures: run.failures,
    truncated: run.truncated_queries,
    reduced: run.reduced_queries,
    disk: run.largest_database_bytes,
    diskScope: run.database_scope,
    startupP95: run.startup_latency_ms?.p95 ?? null,
    writeP95: run.write_latency_ms?.p95 ?? null,
    writeUnit: run.write_latency_unit,
    writeThroughput: run.write_throughput_records_per_second,
    binary:
      run.provider === 'instantkv'
        ? 'binary_bytes' in run.resources[0]
          ? run.resources[0].binary_bytes
          : null
        : null,
    rssScope: run.rss_scope,
    samples: run.query_samples,
    repetitions: run.repetitions,
    raw: '/benchmark-data/full-retrieval/runtime-metrics.json',
    context:
      run.provider === 'sqlite-fts5'
        ? 'In-process · shared host load'
        : 'Loopback HTTP · shared host load',
  };
});
const irRows: RuntimeRow[] = secondary.flatMap((row) => {
  return [row.report.providers.instantkv, row.report.providers.supermemory].map(
    (outer, i) => {
      const nested = i === 0 ? row.native : row.control;
      return {
        suite: row.name,
        provider: i === 0 ? 'instantKV' : 'Supermemory local',
        recall: nested.metrics.recall_at_10,
        ndcg: nested.metrics.ndcg_at_10,
        latency: nested.query_latency_ms,
        rss: outer.largest_sampled_rss_bytes,
        failures: outer.errors,
        truncated: 'truncated_queries' in outer ? outer.truncated_queries : 0,
        reduced: 'reduced_queries' in outer ? outer.reduced_queries : 0,
        disk: 'database_bytes' in outer ? outer.database_bytes : null,
        diskScope: 'One full corpus database',
        startupP95: null,
        writeP95: 'save_latency_ms' in outer ? outer.save_latency_ms.p95 : null,
        writeUnit: 'Record request; provider commit guarantees differ',
        writeThroughput:
          'ingestion_total_ms' in outer
            ? outer.saved_chunks / (outer.ingestion_total_ms / 1000)
            : null,
        binary: outer.binary_bytes,
        rssScope:
          i === 0
            ? 'Native Rust server'
            : 'Server + descendants, embedding runtime included',
        samples: row.report.test_queries,
        repetitions: 1,
        raw: row.raw,
        context:
          i === 0
            ? 'Current native run · loopback HTTP'
            : 'Recorded 3 October control · loopback HTTP',
      };
    },
  );
});
export const runtimeRows = [...fullRows, ...irRows];
export const highestObserved = (row: RuntimeRow, metric: 'recall' | 'ndcg') =>
  row[metric] ===
  Math.max(
    ...runtimeRows.filter((r) => r.suite === row.suite).map((r) => r[metric]),
  );
export const nativeRuntime = runtimeRows.filter(
  (row) => row.provider === 'instantKV',
);
