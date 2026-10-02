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
  const index = `# instantKV\n\nLocal-first memory for local LLMs. Source MVP, unreleased; earlier 0.1.2 archives lack the new memory tools. remember/recall/browse/forget through Rust, HTTP, CLI and MCP. Indexed topics, tags and Unix-ms event times; bounded literal keyword filtering, not semantic search. Custom JSON metadata, namespace grants, configurable query and storage budgets. Offline operation requires no model or embedding service. The runtime decides what to save and inserts recalled facts into context.\n\nThree 10,000-memory warm synthetic Mac runs: topic query p95 ${topicRange} ms, largest sampled server RSS ${sampledRam} MiB, all ${recovered} memories recovered after abrupt restart. Excludes inference, energy and phones. Native Swift/Kotlin bindings and real local-model quality evaluation remain planned. ARM-board goals are explicitly unverified. Browser replay is the older raw-KV workload, not indexed retrieval.\n\n## Documentation\n\n${docs.map((d) => `- [${d.title}](https://instantkv.com/docs/${d.slug}/): ${d.description}`).join('\n')}\n\n- [Structured-memory raw report](https://instantkv.com/benchmark-data/memory/mac-arm64.json)\n- [Recorded KV demo](https://instantkv.com/demo/)\n- [Measured benchmarks](https://instantkv.com/benchmarks/)\n- [Complete Markdown](https://instantkv.com/llms-full.txt)\n- [Source](${repository})\n`;
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
