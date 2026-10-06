import { repository } from './docs.ts';

export const origin = 'https://instantkv.com';
export const projectDescription =
  'Open-source local AI memory for agents. Install a Rust service with MCP, HTTP, CLI and an embedded core. Structured recall, BM25 search and durable checkpoints.';

export function isIndexable(path: string): boolean {
  return ![
    '/404.html',
    '/404/',
    '/search/',
    '/docs/checkpoints/',
    '/docs/distributed-memory/',
  ].includes(path);
}

export function structuredData(
  path: string,
  title: string,
  description: string,
) {
  const canonical = new URL(path, origin).href;
  const source = origin + '/#source';
  const website = origin + '/#website';
  const guide = path.startsWith('/docs/') && path !== '/docs/';
  const breadcrumbs = [
    { '@type': 'ListItem', position: 1, name: 'instantKV', item: origin + '/' },
  ];
  if (guide)
    breadcrumbs.push({
      '@type': 'ListItem',
      position: 2,
      name: 'Documentation',
      item: origin + '/docs/',
    });
  if (path !== '/')
    breadcrumbs.push({
      '@type': 'ListItem',
      position: breadcrumbs.length + 1,
      name: title,
      item: canonical,
    });
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'WebSite',
        '@id': website,
        name: 'instantKV',
        url: origin + '/',
        description: projectDescription,
        inLanguage: 'en',
        about: { '@id': source },
      },
      {
        '@type': 'SoftwareSourceCode',
        '@id': source,
        name: 'instantKV',
        url: origin + '/',
        codeRepository: repository,
        license: repository + '/blob/main/LICENSE',
        programmingLanguage: 'Rust',
        runtimePlatform: 'Native Rust service or in-process Rust core',
        version: 'Unreleased structured-memory source MVP',
        description: projectDescription,
        keywords: [
          'local AI memory',
          'agent memory',
          'MCP',
          'BM25',
          'checkpoints',
        ],
      },
      {
        '@type': guide ? ['WebPage', 'TechArticle'] : 'WebPage',
        '@id': canonical + '#page',
        url: canonical,
        name: title,
        description,
        inLanguage: 'en',
        isPartOf: { '@id': website },
        about: { '@id': source },
        ...(path === '/' ? { mainEntity: { '@id': source } } : {}),
        breadcrumb: { '@id': canonical + '#breadcrumbs' },
      },
      {
        '@type': 'BreadcrumbList',
        '@id': canonical + '#breadcrumbs',
        itemListElement: breadcrumbs,
      },
    ],
  };
}

// JSON-LD is inert data. Escape HTML delimiters so values cannot close its tag.
export function serializeStructuredData(value: unknown): string {
  return JSON.stringify(value)
    .replaceAll('<', '\\u003c')
    .replaceAll('>', '\\u003e')
    .replaceAll('&', '\\u0026');
}
