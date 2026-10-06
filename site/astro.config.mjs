import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { unified } from '@astrojs/markdown-remark';
import { cpSync, mkdirSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { docs, repository } from './src/lib/docs.ts';
import { isIndexable } from './src/lib/discovery.ts';
import { rewriteRepositoryLinks } from './src/lib/repository-links.mjs';
import { prepareAgentContent } from './scripts/agent-content.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
function repositoryLinks() {
  return (tree, file) => {
    if (tree.children[0]?.type === 'heading' && tree.children[0].depth === 1)
      tree.children.shift();
    rewriteRepositoryLinks(tree, file.path, { root, docs, repository });
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
  prepareAgentContent(root, target, docs, repository);
}
export default defineConfig({
  site: 'https://instantkv.com',
  output: 'static',
  trailingSlash: 'always',
  vite: { build: { assetsInlineLimit: 0 } },
  integrations: [
    sitemap({ filter: (url) => isIndexable(new URL(url).pathname) }),
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
