import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { docs } from '../src/lib/docs.ts';
import { isIndexable } from '../src/lib/discovery.ts';
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';

const root = resolve('dist');
assert(existsSync(root), 'Run npm run build before verification');
function files(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = resolve(directory, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}
const htmlFiles = files(root).filter((path) => path.endsWith('.html'));
const failures = [];
for (const file of htmlFiles) {
  const html = readFileSync(file, 'utf8');
  const page = file.slice(root.length).replace(/index\.html$/, '');
  assert.equal(
    (html.match(/<h1[\s>]/g) || []).length,
    1,
    `${page}: one visible page heading`,
  );
  assert(html.includes('name="description"'), `${page}: description metadata`);
  assert(
    html.includes('Local-first agent memory.'),
    `${page}: local-first product positioning`,
  );
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
  const dataScripts = scripts.filter(([, attrs]) =>
    /type="application\/ld\+json"/.test(attrs),
  );
  assert.equal(dataScripts.length, 1, page + ': one JSON-LD entity graph');
  for (const [, attrs, body] of scripts) {
    if (/type="application\/ld\+json"/.test(attrs)) {
      const graph = JSON.parse(body);
      assert.equal(graph['@context'], 'https://schema.org');
      assert(
        graph['@graph'].some(
          (entity) => entity['@type'] === 'SoftwareSourceCode',
        ),
      );
      const webPage = graph['@graph'].find((entity) =>
        entity['@id']?.endsWith('#page'),
      );
      assert.equal(webPage.url, 'https://instantkv.com' + page);
    } else {
      assert(
        /\bsrc=/.test(attrs),
        page + ': executable scripts must be external',
      );
      assert.equal(body.trim(), '', page + ': no inline executable content');
    }
  }
  assert(
    html.includes('rel="canonical" href="https://instantkv.com' + page + '"'),
    page + ': canonical URL',
  );
  assert.equal(
    html.includes('content="noindex, follow"'),
    !isIndexable(page),
    page + ': indexing policy',
  );
  for (const match of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
    const value = match[1].replaceAll('&amp;', '&');
    if (/^(?:[a-z]+:|\/\/)/i.test(value)) continue;
    const url = new URL(value, 'https://instantkv.com' + page);
    const pathname = decodeURIComponent(url.pathname);
    let target = resolve(root, '.' + pathname);
    if (existsSync(target) && statSync(target).isDirectory())
      target = resolve(target, 'index.html');
    if (!existsSync(target)) {
      failures.push(`${page} -> ${value}`);
      continue;
    }
    if (url.hash && target.endsWith('.html')) {
      const id = decodeURIComponent(url.hash.slice(1));
      const document = readFileSync(target, 'utf8');
      if (!document.includes(`id="${id}"`))
        failures.push(`${page} -> missing anchor ${value}`);
    }
  }
}
assert.deepEqual(
  failures,
  [],
  'Rendered internal links, anchors and assets must resolve',
);
const memoryReport = JSON.parse(
  readFileSync(resolve(root, 'benchmark-data/memory/mac-arm64.json'), 'utf8'),
);
assert.equal(memoryReport.runs.length, 3);
assert.equal(
  memoryReport.runs.reduce(
    (n, run) => n + run.exact_memories_after_kill_restart,
    0,
  ),
  30000,
);
assert(
  memoryReport.runs.every((run) => run.errors === 0 && run.mcp_bridge_verified),
);
const agentDocs = readFileSync(resolve(root, 'llms-full.txt'), 'utf8');
assert(agentDocs.includes('# Memory for local LLMs'));
assert(agentDocs.includes('# Performance: measured and planned'));
assert(agentDocs.includes('unreleased'));
const memorySchema = JSON.parse(
  readFileSync(resolve(root, 'examples/memory.schema.json'), 'utf8'),
);
assert(memorySchema.remember && memorySchema.recall && memorySchema.search);
const rankedReport = JSON.parse(
  readFileSync(resolve(root, 'benchmark-data/search/scifact.json'), 'utf8'),
);
assert(rankedReport.complete);
assert.equal(rankedReport.test_queries, 300);
assert(
  rankedReport.providers.instantkv.scifact.queries.every(
    (q) => !q.work.truncated,
  ),
);
assert(
  memoryReport.runs.every(
    (run) =>
      run.verified_deleted_memories === 300 &&
      run.verified_remaining_memories === 9700,
  ),
);
assert(!existsSync(resolve(root, 'demo/index.html')));
assert(!existsSync(resolve(root, 'recordings')));
for (const route of ['index.html', 'benchmarks/index.html']) {
  const page = readFileSync(resolve(root, route), 'utf8');
  assert(
    !page.includes('100,000 cache') && !page.includes('raw KV API'),
    'Product pages use current memory workloads',
  );
}
assert(
  existsSync(resolve(root, 'pagefind/pagefind.js')),
  'Search index exists',
);
assert(
  readFileSync(resolve(root, 'llms-full.txt'), 'utf8').includes(
    '# HTTP reference',
  ),
);
assert(existsSync(resolve(root, 'sitemap-index.xml')));
assert(
  !files(root).some((path) => /(?:credentials|\.env$|\.redb$)/.test(path)),
  'No node credentials or memory data in site',
);

const suiteInputs = JSON.parse(
  readFileSync(resolve(root, 'benchmark-data/suite/inputs.json'), 'utf8'),
);
const suiteNames = ['nfcorpus', 'arguana', 'locomo', 'longmemeval'];
const suiteReceipt = JSON.parse(
  readFileSync(resolve(root, 'benchmark-data/suite/verification.json'), 'utf8'),
);
for (const name of suiteNames) {
  const raw = readFileSync(resolve(root, `benchmark-data/suite/${name}.json`));
  const report = JSON.parse(raw.toString('utf8'));
  assert.equal(
    report.dataset_sha256,
    suiteInputs.datasets[name].normalized_sha256,
  );
  assert.equal(report.runtime_dirty, false);
  assert(report.complete, `${name}: complete before publication`);
  for (const provider of Object.values(report.providers)) {
    assert.equal(provider.queries.length, report.test_queries);
    assert.equal(provider.saved_chunks, report.stored_chunks);
    assert.equal(provider.errors, 0);
  }
  const receipt = suiteReceipt.reports.find((r) => r.report === `${name}.json`);
  assert.equal(receipt?.source_inputs_verified, true);
  assert(receipt, `${name}: independent score verification`);
  const { createHash } = await import('node:crypto');
  assert.equal(createHash('sha256').update(raw).digest('hex'), receipt.sha256);
}
const v2Receipt = JSON.parse(
  readFileSync(
    resolve(root, 'benchmark-data/search-v2/default/verification.json'),
    'utf8',
  ),
);
for (const name of suiteNames) {
  const raw = readFileSync(
    resolve(root, `benchmark-data/search-v2/default/${name}.json`),
  );
  const report = JSON.parse(raw.toString('utf8'));
  assert(report.complete && !report.runtime_dirty);
  assert.equal(
    report.dataset_sha256,
    suiteInputs.datasets[name].normalized_sha256,
  );
  assert.equal(report.providers.instantkv.contract_rejections, 0);
  assert.equal(report.providers.instantkv.queries.length, report.test_queries);
  assert.equal(report.providers.instantkv.errors, 0);
  assert(
    report.providers.supermemory.historical_control,
    'Reference is explicitly historical',
  );
  const receipt = v2Receipt.reports.find((r) => r.report === `${name}.json`);
  assert(receipt?.source_inputs_verified);
  const { createHash } = await import('node:crypto');
  assert.equal(createHash('sha256').update(raw).digest('hex'), receipt.sha256);
  for (const query of report.providers.instantkv.queries) {
    assert(query.work.selected_terms <= 64 && query.work.expansion_terms <= 8);
  }
}
const expandedRaw = readFileSync(
  resolve(root, 'benchmark-data/search-v2/expansion/arguana.json'),
);
const expandedReceipt = JSON.parse(
  readFileSync(
    resolve(root, 'benchmark-data/search-v2/expansion/verification.json'),
    'utf8',
  ),
);
const { createHash } = await import('node:crypto');
assert.equal(
  createHash('sha256').update(expandedRaw).digest('hex'),
  expandedReceipt.reports[0].sha256,
);
assert(expandedReceipt.reports[0].source_inputs_verified);
const article = readFileSync(
  resolve(root, 'blog/lightweight-memory-benchmarks/index.html'),
  'utf8',
);
assert(!article.includes('_PENDING'), 'Article has no incomplete sections');
assert(
  article.includes('500') &&
    article.toLowerCase().includes('rejected') &&
    article.includes('85.20%'),
  'Article includes scope and query failures',
);

const fullSummary = JSON.parse(
  readFileSync(
    resolve(root, 'benchmark-data/full-retrieval/summary.json'),
    'utf8',
  ),
);
const fullReceipt = JSON.parse(
  readFileSync(
    resolve(root, 'benchmark-data/full-retrieval/verification.json'),
    'utf8',
  ),
);
assert.equal(Object.keys(fullReceipt.receipts).length, 5);
for (const [name, hash] of Object.entries(fullSummary.ranking_sha256)) {
  const raw = readFileSync(
    resolve(root, 'benchmark-data/full-retrieval', name),
  );
  assert.equal(createHash('sha256').update(raw).digest('hex'), hash);
  const receipt = fullReceipt.receipts[name];
  assert(receipt?.verified, `${name}: official source labels verified`);
}
for (const file of htmlFiles) {
  const html = readFileSync(file, 'utf8');
  assert(
    !/href="\/(?:demo|docs\/(?:live-demo|demo))\//.test(html),
    'No retired demo navigation',
  );
}
const home = readFileSync(resolve(root, 'index.html'), 'utf8');
assert(home.includes('95.13') && home.includes('14.34'));
assert(!home.includes('91.67') && !home.includes('65.28'));
assert(
  home
    .replace(/\\\n\s*/g, '')
    .includes(
      'cargo install --git https://github.com/maskjelly/instantKV --locked instantkv',
    ),
);
assert(home.includes('unreleased source MVP') && home.includes('v0.1.2'));
assert(
  home.indexOf('id="install-title"') < home.indexOf('id="evidence-title"'),
);
assert(!home.includes('local-devices-hero.webp'));

const resources = JSON.parse(
  readFileSync(
    resolve(root, 'benchmark-data/full-retrieval/runtime-metrics.json'),
    'utf8',
  ),
);
assert.equal(resources.runs.length, 5);
const percentile = (values, p) =>
  [...values].sort((a, b) => a - b)[Math.ceil((values.length * p) / 100) - 1];
for (const run of resources.runs) {
  const rankingFile = `${run.suite}--${run.provider}.json`;
  assert.equal(run.ranking_sha256, fullSummary.ranking_sha256[rankingFile]);
  assert.equal(run.query_samples, run.queried_questions * run.repetitions);
  assert.equal(run.query_latency_samples_ms.length, run.query_samples);
  for (const p of [50, 95, 99])
    assert.equal(
      run.query_latency_ms[`p${p}`],
      percentile(run.query_latency_samples_ms, p),
    );
  assert.equal(
    run.largest_sampled_rss_bytes,
    Math.max(...run.resources.map((r) => r.largest_sampled_rss_bytes)),
  );
  assert.equal(
    run.largest_database_bytes,
    Math.max(...run.resources.map((r) => r.database_bytes)),
  );
  const writes = run.resources.flatMap((r) => r.write_latency_samples_ms);
  for (const p of [50, 95, 99])
    assert.equal(run.write_latency_ms[`p${p}`], percentile(writes, p));
}
const qa = JSON.parse(
  readFileSync(
    resolve(root, 'benchmark-data/full-retrieval/qa-summary.json'),
    'utf8',
  ),
);
assert(qa.complete && qa.questions === 500);
for (const [file, hash] of Object.entries(qa.raw_sha256))
  assert.equal(
    createHash('sha256')
      .update(
        readFileSync(resolve(root, 'benchmark-data/full-retrieval', file)),
      )
      .digest('hex'),
    hash,
  );
const answers = readFileSync(
  resolve(
    root,
    'benchmark-data/full-retrieval/longmemeval-s--instantkv--qa.jsonl',
  ),
  'utf8',
)
  .trim()
  .split('\n')
  .map((line) => JSON.parse(line));
assert.equal(answers.length, 500);
assert.equal(new Set(answers.map((row) => row.question_id)).size, 500);
assert.equal(
  answers.reduce((sum, row) => sum + row.score, 0),
  qa.correct,
);
assert.equal(qa.qa_score, qa.correct / 500);
assert.equal(answers.filter((row) => row.failure).length, qa.qa_failures);
const benchPage = readFileSync(resolve(root, 'benchmarks/index.html'), 'utf8');
assert(
  benchPage.includes('Sampled RAM') &&
    benchPage.includes('p99') &&
    benchPage.includes('Highest observed'),
);
assert(benchPage.includes('85.20') && benchPage.includes('CPU utilization'));

console.log(
  `Verified ${htmlFiles.length} HTML pages, their local links/anchors/assets, current memory and retrieval reports, search and machine-readable docs.`,
);

// Discovery is a built-output contract, not a ranking assertion.
const sitemapFiles = files(root).filter((path) =>
  /sitemap-\d+\.xml$/.test(path),
);
const sitemapURLs = sitemapFiles.flatMap((file) =>
  [...readFileSync(file, 'utf8').matchAll(/<loc>([^<]+)<\/loc>/g)].map(
    (match) => match[1],
  ),
);
for (const file of htmlFiles) {
  const page = file.slice(root.length).replace(/index\.html$/, '');
  assert.equal(
    sitemapURLs.includes('https://instantkv.com' + page),
    isIndexable(page),
    page + ': sitemap matches robots metadata',
  );
}
const parser = unified().use(remarkParse).use(remarkGfm);
let exportLinks = 0;
for (const doc of docs) {
  const pathname = '/docs/' + doc.slug + '/index.md';
  const markdown = readFileSync(resolve(root, '.' + pathname), 'utf8');
  const html = readFileSync(
    resolve(root, 'docs', doc.slug, 'index.html'),
    'utf8',
  );
  assert(
    html.includes(
      'rel="alternate" type="text/markdown" href="' + pathname + '"',
    ),
    doc.slug + ': discoverable Markdown',
  );
  assert(
    markdown.includes(
      'Canonical page: https://instantkv.com/docs/' + doc.slug + '/',
    ),
  );
  function visit(node) {
    if (['link', 'image', 'definition'].includes(node.type) && node.url) {
      assert(
        /^[a-z]+:/i.test(node.url),
        doc.slug + ': absolute export link ' + node.url,
      );
      const url = new URL(node.url);
      if (url.origin === 'https://instantkv.com') {
        let target = resolve(root, '.' + decodeURIComponent(url.pathname));
        if (existsSync(target) && statSync(target).isDirectory())
          target = resolve(target, 'index.html');
        assert(
          existsSync(target),
          doc.slug + ': exported resource exists: ' + node.url,
        );
        if (url.hash) {
          const page = target.endsWith('.md')
            ? target.replace(/index\.md$/, 'index.html')
            : target;
          if (page.endsWith('.html'))
            assert(
              readFileSync(page, 'utf8').includes(
                'id="' + decodeURIComponent(url.hash.slice(1)) + '"',
              ),
              doc.slug + ': exported anchor exists ' + node.url,
            );
        }
        exportLinks++;
      }
    }
    for (const child of node.children || []) visit(child);
  }
  visit(parser.parse(markdown));
}
const index = readFileSync(resolve(root, 'llms.txt'), 'utf8');
assert(Buffer.byteLength(index) < 6000, 'Agent index must stay bounded');
assert(index.startsWith('# instantKV\n\n>'));
assert(index.includes('mcp-local --dir'));
assert(index.includes('Source MVP, unreleased'));
console.log(
  'Discovery verified: ' +
    docs.length +
    ' Markdown guides, ' +
    exportLinks +
    ' internal export links, ' +
    sitemapURLs.length +
    ' indexable pages.',
);
