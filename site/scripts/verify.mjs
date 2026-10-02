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
const reports = files(resolve(root, 'benchmark-data'))
  .filter((path) => /-\d\.json$/.test(path))
  .map((path) => JSON.parse(readFileSync(path, 'utf8')));
assert.equal(reports.length, 15);
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
assert.equal(
  reports.reduce((sum, report) => sum + report.successful_requests, 0),
  157500,
);
assert.equal(
  reports.reduce((sum, report) => sum + report.errors, 0),
  0,
);
const recordingFiles = files(resolve(root, 'recordings/mac')).filter((path) =>
  /(?:cache|durable)-\d\.json$/.test(path),
);
assert.equal(recordingFiles.length, 6);
const recordings = recordingFiles.map((path) =>
  JSON.parse(readFileSync(path, 'utf8')),
);
assert.equal(
  recordings.reduce((sum, report) => sum + report.written, 0),
  330000,
);
assert.equal(
  recordings.reduce((sum, report) => sum + report.errors, 0),
  0,
);
const replay = JSON.parse(
  readFileSync(resolve(root, 'recordings/mac/replay.json'), 'utf8'),
);
assert.equal(replay.recordings.cache.count, 100000);
assert.equal(replay.recordings.durable.count, 10000);
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
  `Verified ${htmlFiles.length} HTML pages, their local links/anchors/assets, 15 raw reports, search and machine-readable docs.`,
);
