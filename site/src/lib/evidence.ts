import full from '../../../docs/benchmarks/2026-10-04-full-retrieval/summary.json';
import scifact from '../../../docs/benchmarks/2026-10-04-search/scifact.json';
import arguana from '../../../docs/benchmarks/2026-10-04-search/default/arguana.json';
import nfcorpus from '../../../docs/benchmarks/2026-10-04-search/default/nfcorpus.json';
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
