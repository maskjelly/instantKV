import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';
import { docs, repository } from '../src/lib/docs.ts';
import {
  isIndexable,
  serializeStructuredData,
  structuredData,
} from '../src/lib/discovery.ts';
import { exportMarkdown } from './agent-content.mjs';
import { resolveRepositoryLink } from '../src/lib/repository-links.mjs';

const root = resolve('..');
const options = { root, docs, repository };
const source = resolve(root, 'docs/agents.md');

test('Markdown exports resolve guides, references, assets and fragments', () => {
  const input = [
    '# Guide',
    '[setup](quickstart.md#local-install)',
    '[reference][setup]',
    '[setup]: memory-mvp.md',
    '![diagram](assets/blueprint-mark.svg)',
    '[section](#agent-instruction)',
    '[schema](../examples/memory.schema.json)',
  ].join('\n\n');
  const output = exportMarkdown(input, source, options);
  assert(
    output.includes(
      'https://instantkv.com/docs/quickstart/index.md#local-install',
    ),
  );
  assert(
    output.includes('[setup]: https://instantkv.com/docs/memory-mvp/index.md'),
  );
  assert(output.includes('https://instantkv.com/assets/blueprint-mark.svg'));
  assert(
    output.includes('https://instantkv.com/docs/agents/#agent-instruction'),
  );
  assert(output.includes('https://instantkv.com/examples/memory.schema.json'));
});

test('Markdown export preserves executable examples and GFM tables', () => {
  const fence = String.fromCharCode(96).repeat(3);
  const code = 'echo "[not a link](quickstart.md)"';
  const output = exportMarkdown(
    fence +
      'sh\n' +
      code +
      '\n' +
      fence +
      '\n\n| Operation | Meaning |\n| --- | --- |\n| search | BM25 |\n',
    source,
    options,
  );
  assert(output.includes(code));
  assert(!output.includes('https://instantkv.com/docs/quickstart/'));
  assert(output.includes('| search'));
  assert(output.includes('BM25'));
});

test('HTML and Markdown use the same source route and nested report mapping', () => {
  assert.equal(
    resolveRepositoryLink('memory-mvp.md#limits', source, options),
    '/docs/memory-mvp/#limits',
  );
  assert.equal(
    resolveRepositoryLink(
      'benchmarks/2026-10-04-search/controls/README.md',
      source,
      options,
    ),
    '/benchmark-data/search-v2/controls/README.md',
  );
  assert.equal(
    resolveRepositoryLink('../crates/instantkv/src/mcp.rs', source, options),
    repository + '/blob/main/crates/instantkv/src/mcp.rs',
  );
});

test('Source entity identifies unreleased memory code without sales or ranking claims', () => {
  const value = structuredData(
    '/docs/agents/',
    'Connect through MCP',
    'Local tools.',
  );
  const entity = value['@graph'].find(
    (item) => item['@type'] === 'SoftwareSourceCode',
  );
  assert.equal(entity.codeRepository, repository);
  assert.equal(entity.version, 'Unreleased structured-memory source MVP');
  assert.equal(entity.programmingLanguage, 'Rust');
  assert(!entity.offers && !entity.aggregateRating && !entity.review);
  const crumbs = value['@graph'].find(
    (item) => item['@type'] === 'BreadcrumbList',
  );
  assert.equal(
    crumbs.itemListElement.at(-1).item,
    'https://instantkv.com/docs/agents/',
  );
});

test('JSON-LD cannot terminate its inert script element', () => {
  const malicious = { text: '</script><script>alert(1)</script>&' };
  const encoded = serializeStructuredData(malicious);
  assert(!encoded.includes('<'));
  assert.deepEqual(JSON.parse(encoded), malicious);
});

test('Only current useful HTML pages enter the sitemap', () => {
  for (const path of [
    '/search/',
    '/404.html',
    '/docs/checkpoints/',
    '/docs/distributed-memory/',
  ])
    assert.equal(isIndexable(path), false, path);
  for (const path of ['/', '/docs/', '/docs/agents/', '/benchmarks/'])
    assert.equal(isIndexable(path), true, path);
  assert(readFileSync('public/robots.txt', 'utf8').includes('Allow: /'));
});
