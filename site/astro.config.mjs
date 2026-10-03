import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { unified } from '@astrojs/markdown-remark';
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { docs, repository } from './src/lib/docs.ts';

const root = fileURLToPath(new URL('../', import.meta.url));
function repositoryLinks() {
  return (tree, file) => {
    if (tree.children[0]?.type === 'heading' && tree.children[0].depth === 1)
      tree.children.shift();
    function visit(node) {
      if (
        (node.type === 'link' || node.type === 'image') &&
        node.url &&
        !/^(?:[a-z]+:|#|\/)/i.test(node.url)
      ) {
        const [pathname, fragment] = node.url.split('#');
        const source = relative(
          root,
          resolve(dirname(file.path), decodeURI(pathname)),
        ).replaceAll('\\', '/');
        const guide = docs.find((d) => d.source === source);
        if (guide)
          node.url = `/docs/${guide.slug}/${fragment ? '#' + fragment : ''}`;
        else if (
          source.startsWith('docs/assets/') &&
          /\.(png|svg|webp|jpg)$/.test(source)
        )
          node.url = '/assets/' + source.slice('docs/assets/'.length);
        else if (
          source.startsWith('docs/benchmarks/2026-10-04-full-retrieval/')
        )
          node.url =
            '/benchmark-data/full-retrieval/' + source.split('/').at(-1);
        else if (source.startsWith('docs/benchmarks/2026-10-03-memory/'))
          node.url = '/benchmark-data/previous/' + source.split('/').at(-1);
        else if (source.startsWith('docs/benchmarks/2026-10-04-search/'))
          node.url =
            '/benchmark-data/search-v2/' +
            source.slice('docs/benchmarks/2026-10-04-search/'.length);
        else if (source.startsWith('docs/benchmarks/2026-10-03-suite/'))
          node.url = '/benchmark-data/suite/' + source.split('/').at(-1);
        else if (source.startsWith('docs/benchmarks/2026-10-03-ranked/'))
          node.url =
            (source.endsWith('mac-arm64.json')
              ? '/benchmark-data/memory/'
              : '/benchmark-data/search/') + source.split('/').at(-1);
        else if (source.startsWith('examples/')) node.url = '/' + source;
        else
          node.url = `${repository}/${existsSync(resolve(root, source)) && statSync(resolve(root, source)).isDirectory() ? 'tree' : 'blob'}/main/${source}${fragment ? '#' + fragment : ''}`;
      }
      for (const child of node.children || []) visit(child);
    }
    visit(tree);
  };
}
function prepareAssets() {
  const target = fileURLToPath(new URL('./public/', import.meta.url));
  mkdirSync(target, { recursive: true });
  cpSync(resolve(root, 'docs/assets'), resolve(target, 'assets'), {
    recursive: true,
    filter: (path) => !path.endsWith('.tsrct'),
  });
  rmSync(resolve(target, 'benchmark-data'), { recursive: true, force: true });
  rmSync(resolve(target, 'recordings'), { recursive: true, force: true });
  cpSync(
    resolve(root, 'docs/benchmarks/2026-10-03-ranked'),
    resolve(target, 'benchmark-data/memory'),
    { recursive: true },
  );
  cpSync(
    resolve(root, 'docs/benchmarks/2026-10-03-ranked'),
    resolve(target, 'benchmark-data/search'),
    { recursive: true },
  );
  cpSync(
    resolve(root, 'docs/benchmarks/2026-10-03-memory'),
    resolve(target, 'benchmark-data/previous'),
    { recursive: true },
  );
  cpSync(
    resolve(root, 'docs/benchmarks/2026-10-03-suite'),
    resolve(target, 'benchmark-data/suite'),
    { recursive: true },
  );
  cpSync(
    resolve(root, 'docs/benchmarks/2026-10-04-search'),
    resolve(target, 'benchmark-data/search-v2'),
    { recursive: true },
  );
  cpSync(
    resolve(root, 'docs/benchmarks/2026-10-04-full-retrieval'),
    resolve(target, 'benchmark-data/full-retrieval'),
    { recursive: true },
  );
  for (const kind of ['memory', 'search']) {
    for (const name of ['mac-arm64.json', 'scifact.json', 'README.md'])
      cpSync(
        resolve(root, 'docs/benchmarks/2026-10-04-search', name),
        resolve(target, 'benchmark-data', kind, name),
      );
  }
  // This directory is generated; remove stale build artifacts before copying sources.
  rmSync(resolve(target, 'examples'), { recursive: true, force: true });
  cpSync(resolve(root, 'examples'), resolve(target, 'examples'), {
    recursive: true,
    filter: (path) => !path.includes('__pycache__'),
  });
  const full = JSON.parse(
    readFileSync(
      resolve(root, 'docs/benchmarks/2026-10-04-full-retrieval/summary.json'),
      'utf8',
    ),
  );
  const percent = (n) => (100 * n).toFixed(2);
  const index = [
    '# instantKV',
    'Local-first memory for AI agents. One Rust binary. Source MVP, unreleased. Older releases do not include the new memory APIs.',
    'Five memory tools: remember, recall, search, browse and forget. Rust core, HTTP, CLI and MCP. Store content, topic, tags, event time and custom JSON metadata. Topic/tag/time indexes and bounded BM25 with English stemming. Recall uses literal AND filters; search uses OR terms. No embedding model, cloud API or automatic model call is required by the memory service.',
    `Full LongMemEval-S evidence retrieval: all 500 questions. instantKV Recall@10 ${percent(full.suites['longmemeval-s'].instantkv.recall_at_10)}%; SQLite FTS5 ${percent(full.suites['longmemeval-s']['sqlite-fts5'].recall_at_10)}%. Local Supermemory full run is incomplete. Session-level labels, not end-to-end QA.`,
    `Full LoCoMo: all 1,986 questions across ten histories queried; 1,533 have positive source labels. Turn-level Recall@10: instantKV ${percent(full.suites.locomo.instantkv.recall_at_10)}%, SQLite FTS5 ${percent(full.suites.locomo['sqlite-fts5'].recall_at_10)}%, Supermemory local ${percent(full.suites.locomo['supermemory-local'].recall_at_10)}%. All five published retrieval runs have zero failures and zero truncations.`,
    'Independent pytrec_eval verification against official source labels: https://instantkv.com/benchmark-data/full-retrieval/verification.json . Raw rankings and settings: https://instantkv.com/benchmark-data/full-retrieval/summary.json . Read comparison limits before quoting scores. These are retrieval metrics, not official model QA scores. Full native LongMemEval-S QA: 85.20% (426/500), zero API failures, 95% interval 82.0–88.2%. Official judge rubric with GPT-6 Luna reader/judge, not leaderboard model parity. Competitor QA remains incomplete; failed burst API runs do not provide valid comparisons. QA raw outputs: https://instantkv.com/benchmark-data/full-retrieval/qa-summary.json . Runtime resource samples: https://instantkv.com/benchmark-data/full-retrieval/runtime-metrics.json . CPU utilization and energy were not recorded.',
    'Native measured binary 8.31 MiB. Largest sampled Rust server RSS: 14.34 MiB on LongMemEval-S; 11.25 MiB on LoCoMo. Separate three-run 10,000-memory workload: topic query p95 0.152–0.173 ms, durable write p95 6.665–6.923 ms, 30,000/30,000 records recovered after abrupt process restarts. Apple M4 Pro, 24 GiB, macOS 27.0. Sampled RSS is not peak RAM. Parallel competitor timings and differing process scopes do not support speed or RAM ratios.',
    'Supermemory comparisons use local v0.0.8, direct embedding retrieval without model extraction, rewriting or reranking; they do not represent the hosted product. Secondary BEIR results: SciFact 81.43% vs 74.80%; ArguAna 76.96% vs 56.40%; NFCorpus 15.31% vs 17.08%. BEIR controls were recorded separately on 3 October. ArguAna: 688/1,406 truncated queries, 1,149 reduced, zero rejections. Optional English/app expansion is off by default.',
    'Records and indexes change in one redb transaction for writes, deletes and expiry. Keep both get and list permissions for retrieval. Check query_reduced and truncated. Search budgets bound CPU and response size. Custom metadata can extend the schema. Native Swift/Kotlin integration, real phone tests, semantic retrieval and larger-scale tests remain planned.',
    '## Documentation',
    docs
      .map(
        (d) =>
          `- [${d.title}](https://instantkv.com/docs/${d.slug}/): ${d.description}`,
      )
      .join('\n'),
    `- [Benchmarks](https://instantkv.com/benchmarks/)\n- [Engineering notes](https://instantkv.com/blog/lightweight-memory-benchmarks/)\n- [Complete Markdown](https://instantkv.com/llms-full.txt)\n- [Source](${repository})\n`,
  ].join('\n\n');
  writeFileSync(resolve(target, 'llms.txt'), index);
  writeFileSync(
    resolve(target, 'llms-full.txt'),
    index +
      docs
        .map(
          (d) =>
            `\n\n---\nSource: https://instantkv.com/docs/${d.slug}/\n\n${readFileSync(resolve(root, d.source), 'utf8')}`,
        )
        .join(''),
  );
}
export default defineConfig({
  site: 'https://instantkv.com',
  output: 'static',
  trailingSlash: 'always',
  vite: { build: { assetsInlineLimit: 0 } },
  integrations: [
    sitemap(),
    {
      name: 'repository-assets',
      hooks: { 'astro:config:setup': prepareAssets },
    },
  ],
  markdown: {
    processor: unified({ remarkPlugins: [repositoryLinks] }),
    shikiConfig: { theme: 'github-light', wrap: false },
  },
});
