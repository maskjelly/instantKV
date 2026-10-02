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
import { buildReplay } from '../demo/replay-data.mjs';

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
          /\.(png|svg)$/.test(source)
        )
          node.url = '/assets/' + source.slice('docs/assets/'.length);
        else if (source.startsWith('docs/benchmarks/2026-10-03-memory/'))
          node.url = '/benchmark-data/memory/' + source.split('/').at(-1);
        else if (source.startsWith('docs/benchmarks/2026-10-02-local/'))
          node.url = '/benchmark-data/local/' + source.split('/').at(-1);
        else if (
          source.startsWith('docs/benchmarks/') &&
          source.endsWith('.json')
        )
          node.url = '/benchmark-data/' + source.split('/').at(-1);
        else if (source.startsWith('docs/demo-results/2026-10-02-mac/'))
          node.url = '/recordings/mac/' + source.split('/').at(-1);
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
  cpSync(
    resolve(root, 'docs/benchmarks/2026-10-01-rove'),
    resolve(target, 'benchmark-data'),
    { recursive: true },
  );
  cpSync(
    resolve(root, 'docs/benchmarks/2026-10-02-local'),
    resolve(target, 'benchmark-data/local'),
    { recursive: true },
  );
  cpSync(
    resolve(root, 'docs/benchmarks/2026-10-03-memory'),
    resolve(target, 'benchmark-data/memory'),
    { recursive: true },
  );
  // This directory is generated; remove stale build artifacts before copying sources.
  rmSync(resolve(target, 'examples'), { recursive: true, force: true });
  cpSync(resolve(root, 'examples'), resolve(target, 'examples'), {
    recursive: true,
    filter: (path) => !path.includes('__pycache__'),
  });
  const recordings = resolve(root, 'docs/demo-results/2026-10-02-mac');
  cpSync(recordings, resolve(target, 'recordings/mac'), { recursive: true });
  writeFileSync(
    resolve(target, 'recordings/mac/replay.json'),
    JSON.stringify(buildReplay(recordings)),
  );
  const memoryReport = JSON.parse(
    readFileSync(
      resolve(root, 'docs/benchmarks/2026-10-03-memory/mac-arm64.json'),
      'utf8',
    ),
  );
  const p95 = memoryReport.runs.map((run) => run.queries.topic.latency_ms.p95);
  const topicRange = `${Math.min(...p95).toFixed(3)}–${Math.max(...p95).toFixed(3)}`;
  const sampledRam = (
    Math.max(...memoryReport.runs.map((run) => run.largest_sampled_rss_bytes)) /
    1024 ** 2
  ).toFixed(1);
  const recovered = memoryReport.runs
    .reduce((n, run) => n + run.exact_memories_after_kill_restart, 0)
    .toLocaleString('en-US');
  const index = [
    '# instantKV',
    'instantKV stores local-agent memory in one Rust process. The source MVP is unreleased. Earlier 0.1.2 archives do not include the new memory tools.',
    'Use remember, recall, browse and forget through Rust, HTTP, CLI or MCP. Queries use ordered topic/tag/time indexes and bounded literal keyword filtering. Custom JSON metadata and configurable limits support app-specific use. Retrieval requires both get and list grants.',
    'The service needs no cloud API or embedding model. The runtime selects what to save and adds retrieved facts to model context.',
    `Three warm synthetic Mac runs stored 10,000 memories each. Topic query p95 was ${topicRange} ms. The largest sampled server RSS was ${sampledRam} MiB. All ${recovered} memories were recovered after abrupt restarts. These results exclude inference, energy use and phones.`,
    'Linux x86_64, Linux ARM64 and macOS ARM64 passed source MVP CI. ARM-board performance targets remain unverified. Native Swift/Kotlin bindings and real-model quality evaluation are planned. Browser replay uses an older raw KV workload; it does not measure structured-memory retrieval.',
    '## Documentation',
    docs
      .map(
        (d) =>
          `- [${d.title}](https://instantkv.com/docs/${d.slug}/): ${d.description}`,
      )
      .join('\n'),
    `- [Structured-memory raw report](https://instantkv.com/benchmark-data/memory/mac-arm64.json)\n- [Recorded KV demo](https://instantkv.com/demo/)\n- [Measured benchmarks](https://instantkv.com/benchmarks/)\n- [Complete Markdown](https://instantkv.com/llms-full.txt)\n- [Source](${repository})\n`,
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
