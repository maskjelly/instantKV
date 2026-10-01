import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { unified } from '@astrojs/markdown-remark';
import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
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
          /\.(png|svg)$/.test(source)
        )
          node.url = '/assets/' + source.slice('docs/assets/'.length);
        else if (
          source.startsWith('docs/benchmarks/') &&
          source.endsWith('.json')
        )
          node.url = '/benchmark-data/' + source.split('/').at(-1);
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
  cpSync(resolve(root, 'examples'), resolve(target, 'examples'), {
    recursive: true,
  });
  const index = `# instantKV\n\nSelf-hosted knowledge memory for cloud agents. Current release: single-node 0.1.1. Managed hosting and distributed replication are in development.\n\n## Documentation\n\n${docs.map((d) => `- [${d.title}](https://instantkv.com/docs/${d.slug}/): ${d.description}`).join('\n')}\n\n- [Measured benchmarks](https://instantkv.com/benchmarks/)\n- [Complete Markdown](https://instantkv.com/llms-full.txt)\n- [Source](${repository})\n`;
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
    shikiConfig: { theme: 'github-dark', wrap: false },
  },
});
