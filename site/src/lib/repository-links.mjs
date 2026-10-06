import { existsSync, statSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';

export function resolveRepositoryLink(
  url,
  sourcePath,
  { root, docs, repository, markdown = false, absolute = false },
) {
  if (/^(?:[a-z]+:|#|\/)/i.test(url)) {
    if (absolute && url.startsWith('#'))
      return new URL(
        url,
        'https://instantkv.com/docs/' +
          docs.find((d) => resolve(root, d.source) === sourcePath).slug +
          '/',
      ).href;
    if (absolute && url.startsWith('/'))
      return new URL(url, 'https://instantkv.com').href;
    return url;
  }
  const [pathname, fragment] = url.split('#');
  const source = relative(
    root,
    resolve(dirname(sourcePath), decodeURIComponent(pathname)),
  ).replaceAll('\\', '/');
  const guide = docs.find((d) => d.source === source);
  if (guide)
    url = `/docs/${guide.slug}/${markdown ? 'index.md' : ''}${fragment ? '#' + fragment : ''}`;
  else if (
    source.startsWith('docs/assets/') &&
    /\.(png|svg|webp|jpg)$/.test(source)
  )
    url = '/assets/' + source.slice('docs/assets/'.length);
  else if (source.startsWith('docs/benchmarks/2026-10-04-full-retrieval/'))
    url = '/benchmark-data/full-retrieval/' + source.split('/').at(-1);
  else if (source.startsWith('docs/benchmarks/2026-10-03-memory/'))
    url = '/benchmark-data/previous/' + source.split('/').at(-1);
  else if (source.startsWith('docs/benchmarks/2026-10-04-search/'))
    url =
      '/benchmark-data/search-v2/' +
      source.slice('docs/benchmarks/2026-10-04-search/'.length);
  else if (source.startsWith('docs/benchmarks/2026-10-03-suite/'))
    url = '/benchmark-data/suite/' + source.split('/').at(-1);
  else if (source.startsWith('docs/benchmarks/2026-10-03-ranked/'))
    url =
      (source.endsWith('mac-arm64.json')
        ? '/benchmark-data/memory/'
        : '/benchmark-data/search/') + source.split('/').at(-1);
  else if (source.startsWith('examples/')) url = '/' + source;
  else
    url = `${repository}/${existsSync(resolve(root, source)) && statSync(resolve(root, source)).isDirectory() ? 'tree' : 'blob'}/main/${source}${fragment ? '#' + fragment : ''}`;
  return absolute && url.startsWith('/')
    ? new URL(url, 'https://instantkv.com').href
    : url;
}

export function rewriteRepositoryLinks(tree, sourcePath, options) {
  function visit(node) {
    if (['link', 'image', 'definition'].includes(node.type) && node.url)
      node.url = resolveRepositoryLink(node.url, sourcePath, options);
    for (const child of node.children || []) visit(child);
  }
  visit(tree);
  return tree;
}
