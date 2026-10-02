export {};

interface Run {
  id: string;
  mode: string;
  count: number;
  written: number;
  bytes: number;
  expires_at: number;
}
interface Batch {
  written: number;
  total: number;
  bytes: number;
  batch_ms: number;
  operation_ms: number[];
}
const el = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;
const start = el<HTMLButtonElement>('start-run');
const stop = el<HTMLButtonElement>('stop-run');
const newRun = el<HTMLButtonElement>('new-run');
const read = el<HTMLButtonElement>('read-record');
const random = el<HTMLButtonElement>('random-record');
const index = el<HTMLInputElement>('record-index');
const mode = el<HTMLSelectElement>('storage-mode');
const count = el<HTMLSelectElement>('memory-count');
const size = el<HTMLSelectElement>('value-size');
const content = el<HTMLTextAreaElement>('memory-content');
const progress = el<HTMLProgressElement>('write-progress');
const grid = el('memory-grid');
const cells = Array.from({ length: 240 }, () => {
  const cell = document.createElement('span');
  grid.append(cell);
  return cell;
});
const format = (n: number) => n.toLocaleString('en-US');
let run: Run | undefined;
let running = false;
let reading = false;
let paused = false;
let errors = 0;
let activeElapsed = 0;
let operations: number[] = [];
let batches: number[] = [];
const status = (message: string) => {
  el('demo-status').textContent = message;
};
async function api<T>(
  operation: string,
  input: object,
): Promise<{ value: T; ms: number }> {
  const before = performance.now();
  const response = await fetch(`/api/demo/${operation}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(input),
    cache: 'no-store',
    signal: AbortSignal.timeout(30000),
  });
  const value = await response.json();
  if (!response.ok) {
    errors++;
    el('metric-errors').textContent = String(errors);
    throw new Error(value.error || `HTTP ${response.status}`);
  }
  return { value, ms: performance.now() - before };
}
function settings() {
  const locked = running || !!(run && run.written < run.count);
  for (const control of [mode, count, size, content]) control.disabled = locked;
  for (const option of count.options)
    option.disabled = mode.value === 'durable' && Number(option.value) > 10000;
  if (mode.value === 'durable' && Number(count.value) > 10000)
    count.value = '10000';
  if (!running)
    start.textContent =
      run && run.written < run.count
        ? 'Continue loading →'
        : `Store ${format(Number(count.value))} memories →`;
}
function update() {
  if (!run) return;
  progress.max = run.count;
  progress.value = run.written;
  el('write-count').textContent =
    `${format(run.written)} / ${format(run.count)} acknowledged`;
  el('write-percent').textContent =
    `${Math.floor((run.written / run.count) * 100)}%`;
  cells.forEach((cell, i) =>
    cell.classList.toggle(
      'filled',
      run!.written > 0 && (i + 1) / cells.length <= run!.written / run!.count,
    ),
  );
  el('metric-count').textContent = format(run.written);
  el('metric-bytes').textContent = (run.bytes / 1048576).toFixed(2);
  el('metric-rate').textContent = activeElapsed
    ? format(Math.round((operations.length / activeElapsed) * 1000))
    : '—';
  if (operations.length) {
    const sorted = [...operations].sort((a, b) => a - b);
    const percentile = (p: number) =>
      sorted[Math.ceil(sorted.length * p) - 1].toFixed(2);
    el('metric-p50').textContent = percentile(0.5);
    el('metric-p99').textContent = percentile(0.99);
  }
  if (batches.length) {
    const max = Math.max(...batches, 1);
    el('latency-trace').setAttribute(
      'points',
      batches
        .map(
          (ms, i) =>
            `${(i / Math.max(batches.length - 1, 1)) * 1000},${110 - (ms / max) * 100}`,
        )
        .join(' '),
    );
    el('trace-summary').textContent =
      `${batches.length} batches · max ${Math.round(max)} ms`;
  }
  index.disabled = run.written === 0;
  read.disabled = reading || run.written === 0;
  random.disabled = reading || run.written === 0;
  index.max = String(Math.max(run.written - 1, 0));
  el('read-range').textContent = run.written
    ? `0–${format(run.written - 1)}`
    : 'load memories first';
  const tab = el<HTMLAnchorElement>('reader-tab');
  tab.hidden = !run.written;
  tab.href = `/demo/#run=${run.id}`;
}
mode.addEventListener('change', settings);
count.addEventListener('change', settings);
newRun.addEventListener('click', () => {
  if (running || reading) return;
  run = undefined;
  operations = [];
  batches = [];
  activeElapsed = 0;
  errors = 0;
  progress.value = 0;
  cells.forEach((cell) => cell.classList.remove('filled'));
  for (const id of ['metric-count', 'metric-bytes', 'metric-errors'])
    el(id).textContent = '0';
  for (const id of ['metric-rate', 'metric-p50', 'metric-p99'])
    el(id).textContent = '—';
  el('latency-trace').setAttribute('points', '');
  el('trace-summary').textContent = 'No measurements yet';
  el('write-count').textContent =
    `0 / ${format(Number(count.value))} acknowledged`;
  el('write-percent').textContent = '0%';
  el('write-preview').textContent =
    'Start a new run to generate synthetic records.';
  el('read-output').textContent = 'Load a new run before reading.';
  el('read-verification').textContent = 'Waiting for a stored record';
  el('read-browser-ms').textContent = '— ms';
  el('read-backend-ms').textContent = '— ms';
  el<HTMLAnchorElement>('reader-tab').hidden = true;
  index.disabled = true;
  read.disabled = true;
  random.disabled = true;
  history.replaceState(null, '', location.pathname);
  settings();
  status(
    'Choose settings for your new run. Previous runs expire automatically.',
  );
});
stop.addEventListener('click', () => {
  paused = true;
  stop.disabled = true;
  status('Pausing after the current batch is acknowledged…');
});
el('clear-context').addEventListener('click', () => {
  content.value = '';
  el('write-preview').textContent =
    'Local context cleared. Only the session locator remains. Read a record from the independent reader.';
  el('read-output').textContent =
    'Reader context cleared. Fetch a record from storage.';
  el('read-verification').textContent = 'Context cleared · ready to recall';
  el('read-browser-ms').textContent = '— ms';
  el('read-backend-ms').textContent = '— ms';
  status(
    'Local values cleared. Stored keys remain available until expiry or eviction.',
  );
});
start.addEventListener('click', async () => {
  if (running) return;
  running = true;
  paused = false;
  start.disabled = true;
  stop.disabled = false;
  newRun.disabled = true;
  for (const control of [mode, count, size, content]) control.disabled = true;
  try {
    if (!run || run.written === run.count) {
      run = undefined;
      operations = [];
      batches = [];
      activeElapsed = 0;
      errors = 0;
      el('read-output').textContent =
        'Waiting for a stored record in the new run.';
      el('read-verification').textContent = 'Waiting for a stored record';
      el('read-browser-ms').textContent = '— ms';
      el('read-backend-ms').textContent = '— ms';
      el('metric-p50').textContent = '—';
      el('metric-p99').textContent = '—';
      el('metric-errors').textContent = '0';
      const { value } = await api<Run & { preview: object }>('session', {
        mode: mode.value,
        count: Number(count.value),
        valueBytes: Number(size.value),
        content: content.value,
      });
      run = {
        id: value.id,
        expires_at: value.expires_at,
        count: Number(count.value),
        written: 0,
        bytes: 0,
        mode: mode.value,
      };
      el('write-preview').textContent = JSON.stringify(value.preview, null, 2);
      history.replaceState(null, '', `#run=${run.id}`);
      update();
    }
    while (run.written < run.count && !paused) {
      status(
        `Writing ${format(run.count)} ${run.mode === 'cache' ? 'cache' : 'durable'} records…`,
      );
      const { value, ms } = await api<Batch>('write', {
        id: run.id,
        offset: run.written,
      });
      run.written = value.written;
      run.bytes = value.bytes;
      activeElapsed += ms;
      for (const timing of value.operation_ms) operations.push(timing);
      batches.push(ms);
      update();
    }
    status(
      run.written === run.count
        ? `${format(run.written)} memories acknowledged. Clear the local context and recall any exact key.`
        : `Paused at ${format(run.written)} acknowledged memories. You can read now or continue loading.`,
    );
  } catch (error) {
    status(
      error instanceof Error ? error.message : 'Request failed. Try again.',
    );
  } finally {
    running = false;
    start.disabled = false;
    stop.disabled = true;
    newRun.disabled = false;
    for (const control of [mode, count, size, content])
      control.disabled = false;
    settings();
  }
});
async function recall() {
  if (!run || read.disabled) return;
  const requested = Number(index.value);
  if (
    !Number.isInteger(requested) ||
    requested < 0 ||
    requested >= run.written
  ) {
    status('Choose an acknowledged record index.');
    return;
  }
  read.disabled = true;
  random.disabled = true;
  reading = true;
  try {
    const { value, ms } = await api<{
      value: object;
      key: string;
      namespace: string;
      revision: string;
      backend_ms: number;
      verified: boolean;
    }>('read', { id: run.id, index: requested });
    el('read-output').textContent = JSON.stringify(value.value, null, 2);
    el('read-browser-ms').textContent = `${ms.toFixed(1)} ms`;
    el('read-backend-ms').textContent = `${value.backend_ms.toFixed(2)} ms`;
    el('read-verification').textContent = value.verified
      ? '✓ Exact value verified against the generated record'
      : 'Value verification failed';
    el('read-key').textContent =
      `${value.namespace}/${value.key} · revision ${value.revision}`;
    status(`Record ${format(requested)} retrieved from the Rust engine.`);
  } catch (error) {
    el('read-output').textContent =
      'Read failed. No previous value is being displayed.';
    el('read-verification').textContent = 'Read failed';
    status(error instanceof Error ? error.message : 'Read failed.');
  } finally {
    reading = false;
    read.disabled = false;
    random.disabled = false;
  }
}
read.addEventListener('click', recall);
random.addEventListener('click', () => {
  if (run?.written) {
    const sample = crypto.getRandomValues(new Uint32Array(1))[0];
    index.value = String(sample % run.written);
    void recall();
  }
});
const locator = new URLSearchParams(location.hash.slice(1)).get('run');
if (locator && /^[a-f0-9]{48}$/.test(locator)) {
  start.disabled = true;
  api<Run>('status', { id: locator })
    .then(({ value }) => {
      run = value;
      mode.value = value.mode;
      count.value = String(value.count);
      update();
      settings();
      status(
        'Session locator restored. The reader will fetch values from storage.',
      );
    })
    .catch((error: Error) => {
      history.replaceState(null, '', location.pathname);
      status(error.message);
    })
    .finally(() => {
      start.disabled = false;
    });
} else {
  settings();
  start.disabled = false;
}
