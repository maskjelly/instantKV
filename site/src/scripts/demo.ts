export {};
interface Hit {
  key: string;
  revision: number;
  memory: {
    content: string;
    topic: string;
    tags: string[];
    occurred_at_ms: number;
    metadata: { record_id: number };
  };
}
interface Page {
  items: Hit[];
  next_cursor: string | null;
  scanned: number;
  scanned_bytes: number;
  backend_ms: number;
  verified: boolean;
}
interface Run {
  id: string;
  count: number;
  written: number;
  bytes: number;
  expires_at: number;
}
interface Batch {
  written: number;
  total: number;
  bytes: number;
  operation_ms: number[];
}
interface Recording {
  count: number;
  iteration: number;
  preview: object;
  content: string;
  latency_ms: { p50: number; p99: number };
  records_per_second: number;
  reads: (Hit & { index: number; backend_ms: number })[];
  queries: { name: string; input: object; value: Page; client_ms: number }[];
  forgotten: { value: object; absent: object };
}
const el = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;
const source = el<HTMLSelectElement>('demo-source');
const recorded =
  new URLSearchParams(location.search).get('source') === 'recorded';
source.value = recorded ? 'recorded' : 'live';
source.addEventListener('change', () =>
  location.assign(
    source.value === 'recorded' ? '/demo/?source=recorded' : '/demo/',
  ),
);
const start = el<HTMLButtonElement>('start-run'),
  stop = el<HTMLButtonElement>('stop-run'),
  fresh = el<HTMLButtonElement>('new-run');
const count = el<HTMLSelectElement>('memory-count'),
  content = el<HTMLTextAreaElement>('memory-content'),
  index = el<HTMLInputElement>('record-index');
const recall = el<HTMLButtonElement>('recall-memories'),
  browse = el<HTMLButtonElement>('browse-memories'),
  next = el<HTMLButtonElement>('next-page');
const read = el<HTMLButtonElement>('read-record'),
  forget = el<HTMLButtonElement>('forget-record');
const fields = [
  'filter-topic',
  'filter-tag',
  'filter-query',
  'filter-since',
  'filter-until',
];
let run: Run | undefined,
  recording: Recording | undefined,
  page: Page | undefined,
  hit: Hit | undefined;
let running = false,
  querying = false,
  paused = false,
  filters: Record<string, string | number> = {},
  operations: number[] = [];
const status = (s: string) => {
  el('demo-status').textContent = s;
};
const print = (id: string, value: unknown) => {
  el(id).textContent = JSON.stringify(value, null, 2);
};
async function api<T>(operation: string, input: object) {
  const began = performance.now();
  const response = await fetch('/api/demo/' + operation, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input),
    cache: 'no-store',
    signal: AbortSignal.timeout(30000),
  });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'HTTP ' + response.status);
  return { value: value as T, ms: performance.now() - began };
}
const fail = (e: unknown) =>
  status(e instanceof Error ? e.message : 'Request failed. Retry shortly.');
function controls() {
  start.disabled = running || (recorded && !recording);
  stop.disabled = !running;
  fresh.disabled = running || querying;
  count.disabled = recorded || running || !!(run && run.written < run.count);
  content.disabled = recorded || running || !!(run && run.written < run.count);
  recall.disabled =
    browse.disabled =
    read.disabled =
      querying || !(run && run.written);
  next.disabled = querying || !page?.next_cursor;
  forget.disabled =
    recorded ||
    querying ||
    !hit ||
    hit.memory.metadata.record_id !== Number(index.value);
  index.disabled = !(run && run.written);
  index.max = String(Math.max(0, (run?.written || 0) - 1));
  start.textContent =
    run && run.written < run.count
      ? 'Continue →'
      : recorded
        ? 'Open saved run →'
        : 'Remember ' + Number(count.value).toLocaleString('en-US') + ' →';
  const tab = el<HTMLAnchorElement>('reader-tab');
  tab.hidden = recorded || !run?.written;
  if (run) tab.href = '/demo/#run=' + run.id;
}
function progress() {
  const n = run?.written || 0,
    total = run?.count || Number(count.value);
  el<HTMLProgressElement>('write-progress').max = total;
  el<HTMLProgressElement>('write-progress').value = n;
  el('write-count').textContent =
    n.toLocaleString('en-US') +
    ' / ' +
    total.toLocaleString('en-US') +
    ' acknowledged';
  el('write-percent').textContent = Math.floor((n / total) * 100) + '%';
  el('metric-count').textContent = n.toLocaleString('en-US');
  if (operations.length) {
    const values = [...operations].sort((a, b) => a - b);
    el('metric-save').textContent =
      values[Math.ceil(values.length * 0.5) - 1].toFixed(2) +
      ' / ' +
      values[Math.ceil(values.length * 0.99) - 1].toFixed(2);
  }
  controls();
}
function paintPage(value: Page, ms?: number) {
  page = value;
  print('query-output', value);
  el('query-summary').textContent =
    value.items.length +
    ' memories · ' +
    value.scanned +
    ' candidates · ' +
    value.scanned_bytes +
    ' scanned bytes' +
    (value.next_cursor ? ' · more pages available' : ' · end of results');
  el('metric-query').textContent = value.backend_ms.toFixed(3);
  el('metric-client').textContent = recorded ? '—' : ms!.toFixed(2);
  const results = el('memory-results');
  results.replaceChildren();
  for (const item of value.items) {
    const button = document.createElement('button');
    button.type = 'button';
    const label = document.createElement('small');
    label.textContent =
      '#' +
      item.memory.metadata.record_id +
      ' · ' +
      item.memory.topic +
      ' · ' +
      new Date(item.memory.occurred_at_ms).toISOString();
    const text = document.createElement('span');
    text.textContent = item.memory.content.slice(0, 160);
    button.append(label, text);
    button.addEventListener('click', () => {
      index.value = String(item.memory.metadata.record_id);
      void readOne();
    });
    results.append(button);
  }
  if (!value.items.length)
    results.textContent = value.next_cursor
      ? 'No match in this bounded page. Continue with Next page.'
      : 'No memories match these filters.';
  controls();
}
function currentFilters() {
  const result: Record<string, string | number> = {};
  for (const [id, key] of [
    ['filter-topic', 'topic'],
    ['filter-tag', 'tag'],
    ['filter-query', 'query'],
  ]) {
    const value = el<HTMLInputElement>(id).value.trim();
    if (value) result[key] = value;
  }
  for (const [id, key] of [
    ['filter-since', 'since_ms'],
    ['filter-until', 'until_ms'],
  ]) {
    const value = el<HTMLInputElement>(id).value;
    if (value) result[key] = new Date(value).getTime();
  }
  return result;
}
async function query(all = false, continuation = false) {
  if (querying || !run) return;
  querying = true;
  controls();
  try {
    if (recorded) {
      const preset = continuation
        ? 'browse_next'
        : all
          ? 'browse'
          : el<HTMLSelectElement>('query-preset').value;
      const saved = recording!.queries.find((q) => q.name === preset)!;
      paintPage(saved.value);
      if (preset !== 'browse') next.disabled = true;
      status(
        'Saved ' +
          preset +
          ' response. Recorded backend timing; no new storage request.',
      );
    } else {
      if (!continuation) filters = all ? {} : currentFilters();
      if (all)
        fields.forEach((id) => {
          el<HTMLInputElement>(id).value = '';
        });
      const { value, ms } = await api<Page>('query', {
        id: run.id,
        ...filters,
        ...(continuation ? { cursor: page!.next_cursor } : {}),
      });
      paintPage(value, ms);
      status('Rust returned ' + value.items.length + ' verified memories.');
    }
  } catch (e) {
    fail(e);
  } finally {
    querying = false;
    controls();
    if (recorded && page !== recording!.queries[0].value) next.disabled = true;
  }
}
async function readOne() {
  if (querying || !run) return;
  querying = true;
  hit = undefined;
  controls();
  try {
    if (recorded) {
      const saved =
        recording!.reads.find((r) => r.index === Number(index.value)) ||
        recording!.queries
          .flatMap((q) => q.value.items)
          .find((h) => h.memory.metadata.record_id === Number(index.value));
      if (!saved)
        throw new Error(
          'This index was not saved in the recording. Select a recorded result.',
        );
      hit = saved;
      status('Saved storage response. No new storage request.');
    } else {
      const { value } = await api<Hit>('read', {
        id: run.id,
        index: Number(index.value),
      });
      hit = value;
      status('Exact memory fetched from Rust storage.');
    }
    print('read-output', hit);
    el('read-verification').textContent =
      'Verified fields · revision ' + hit.revision;
  } catch (e) {
    el('read-output').textContent =
      e instanceof Error ? e.message : 'Read failed';
    el('read-verification').textContent = 'No memory returned';
    fail(e);
  } finally {
    querying = false;
    controls();
  }
}
function reset() {
  if (running || querying) return;
  run = undefined;
  hit = undefined;
  page = undefined;
  operations = [];
  for (const id of ['write-preview', 'read-output', 'query-output'])
    el(id).textContent = 'No memory loaded.';
  for (const id of ['metric-save', 'metric-query', 'metric-client'])
    el(id).textContent = '—';
  el('memory-results').replaceChildren();
  el('query-summary').textContent = 'Remember some memories first.';
  el('read-verification').textContent =
    'Read a saved memory before deleting it.';
  history.replaceState(null, '', location.pathname + location.search);
  progress();
  status('Ready for a new run. Earlier live memories expire automatically.');
}
start.addEventListener('click', async () => {
  if (running) return;
  if (recorded) {
    reset();
    run = {
      id: 'recorded',
      count: recording!.count,
      written: recording!.count,
      bytes: 0,
      expires_at: 0,
    };
    print('write-preview', recording!.preview);
    progress();
    el('metric-save').textContent =
      recording!.latency_ms.p50.toFixed(2) +
      ' / ' +
      recording!.latency_ms.p99.toFixed(2);
    status(
      'Recorded run ' +
        recording!.iteration +
        ' · 10,000 acknowledged memory saves. Choose a saved query.',
    );
    return;
  }
  if (!run || run.written === run.count) reset();
  running = true;
  paused = false;
  controls();
  try {
    if (!run) {
      const { value } = await api<Run & { preview: object }>('session', {
        count: Number(count.value),
        valueBytes: 512,
        content: content.value,
      });
      run = {
        id: value.id,
        count: value.count,
        written: 0,
        bytes: 0,
        expires_at: value.expires_at,
      };
      print('write-preview', value.preview);
      history.replaceState(null, '', '#run=' + run.id);
    }
    while (run.written < run.count && !paused) {
      status('Remembering through the Rust memory API…');
      const { value } = await api<Batch>('write', {
        id: run.id,
        offset: run.written,
      });
      run.written = value.written;
      run.bytes = value.bytes;
      operations.push(...value.operation_ms);
      progress();
    }
    status(
      paused
        ? 'Paused after an acknowledged batch. Continue to finish.'
        : 'Memories saved. Clear local context, then recall or browse them.',
    );
  } catch (e) {
    fail(e);
  } finally {
    running = false;
    controls();
  }
});
stop.addEventListener('click', () => {
  paused = true;
  stop.disabled = true;
  status('Pausing after this batch is acknowledged…');
});
fresh.addEventListener('click', reset);
count.addEventListener('change', progress);
recall.addEventListener('click', () => void query());
browse.addEventListener('click', () => void query(true));
next.addEventListener('click', () => void query(false, true));
read.addEventListener('click', () => void readOne());
index.addEventListener('input', () => {
  hit = undefined;
  controls();
});
fields.forEach((id) =>
  el(id).addEventListener('input', () => {
    page = undefined;
    next.disabled = true;
  }),
);
el('query-preset').addEventListener('change', () => {
  page = undefined;
  next.disabled = true;
});
el('clear-context').addEventListener('click', () => {
  hit = undefined;
  page = undefined;
  content.value = '';
  el('memory-results').replaceChildren();
  for (const id of ['write-preview', 'read-output', 'query-output'])
    el(id).textContent = 'Displayed context cleared.';
  el('read-verification').textContent = 'Context cleared · ready to read again';
  controls();
  status(
    recorded
      ? 'Displayed context cleared. Recorded responses remain in the browser.'
      : 'Browser values cleared. Live storage can be read using the session locator.',
  );
});
forget.addEventListener('click', async () => {
  if (!run || !hit || recorded || querying) return;
  querying = true;
  controls();
  try {
    const { value } = await api('forget', {
      id: run.id,
      index: Number(index.value),
    });
    print('read-output', value);
    hit = undefined;
    page = undefined;
    el('memory-results').replaceChildren();
    el('query-output').textContent = 'Run a new query after deletion.';
    el('read-verification').textContent = 'Deleted from storage and indexes';
    status('Memory deleted. Read the same key or browse again to verify.');
  } catch (e) {
    fail(e);
  } finally {
    querying = false;
    controls();
  }
});
async function boot() {
  if (recorded) {
    start.disabled = true;
    count.value = '10000';
    count.disabled = content.disabled = true;
    el('live-filters').hidden = true;
    el('recorded-filters').hidden = false;
    el('demo-source-label').textContent =
      'Recorded memory API / saved Mac responses';
    el('source-note').textContent =
      'Three current API runs. Read-only saved responses; no model or live storage calls.';
    el('client-timing-label').textContent = 'Recorded mode';
    el('client-timing-note').textContent = 'No browser storage round-trip';
    try {
      const response = await fetch('/recordings/memory/replay.json');
      if (!response.ok)
        throw new Error('Recording unavailable. Try live mode.');
      const dataset = await response.json();
      recording = dataset.recording;
      content.value = recording!.content;
      progress();
      status(
        'Recording loaded. Open the saved run to inspect real memory responses.',
      );
    } catch (e) {
      fail(e);
    }
  } else {
    const id = new URLSearchParams(location.hash.slice(1)).get('run');
    if (id && /^[a-f0-9]{48}$/.test(id)) {
      try {
        const { value } = await api<Run>('status', { id });
        run = value;
        count.value = String(run.count);
        content.value = '';
        progress();
        status(
          'Independent reader restored. Values will be fetched from Rust.',
        );
      } catch (e) {
        fail(e);
      }
    } else progress();
  }
}
void boot();
