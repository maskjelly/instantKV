import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

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
  assert(
    !/<script\b(?![^>]*\bsrc=)[^>]*>/i.test(html),
    `${page}: scripts must be external for the CSP`,
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
assert(memorySchema.remember && memorySchema.recall);
assert(
  memoryReport.runs.every(
    (run) =>
      run.verified_deleted_memories === 300 &&
      run.verified_remaining_memories === 9700,
  ),
);
const recordingFiles = files(resolve(root, 'recordings/memory')).filter(
  (path) => /memory-\d\.json$/.test(path),
);
assert.equal(recordingFiles.length, 3);
const recordings = recordingFiles.map((path) =>
  JSON.parse(readFileSync(path, 'utf8')),
);
assert.equal(
  recordings.reduce((n, r) => n + r.written, 0),
  30000,
);
assert(
  recordings.every(
    (r) =>
      r.schema_version === 2 &&
      r.errors === 0 &&
      r.queries.length === 7 &&
      r.forgotten.value.deleted,
  ),
);
const replay = JSON.parse(
  readFileSync(resolve(root, 'recordings/memory/replay.json'), 'utf8'),
);
assert.equal(replay.recording.count, 10000);
assert.equal(replay.schema_version, 2);
for (const route of [
  'index.html',
  'benchmarks/index.html',
  'demo/index.html',
]) {
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
console.log(
  `Verified ${htmlFiles.length} HTML pages, their local links/anchors/assets, current memory reports, search and machine-readable docs.`,
);
