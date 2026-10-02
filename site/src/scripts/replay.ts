export {};
interface Sample {
  index: number;
  key: string;
  namespace: string;
  revision: string;
  value: object;
  backend_ms: number;
  verified: boolean;
}
interface Frame {
  written: number;
  bytes: number;
  client_ms: number;
  p50_ms: number;
  p99_ms: number;
}
interface Recording {
  mode: string;
  count: number;
  content: string;
  iteration: number;
  bytes: number;
  elapsed_ms: number;
  records_per_second: number;
  latency_ms: { p50: number; p99: number };
  preview: object;
  batches: Frame[];
  reads: Sample[];
  errors: number;
}
interface Dataset {
  environment: { hardware: { cpu: string }; measured_at: string };
  recordings: Record<string, Recording>;
}
const el = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;
const start = el<HTMLButtonElement>('start-run');
const stop = el<HTMLButtonElement>('stop-run');
const mode = el<HTMLSelectElement>('storage-mode');
const count = el<HTMLSelectElement>('memory-count');
const samples = el<HTMLSelectElement>('recorded-index');
const read = el<HTMLButtonElement>('read-record');
const random = el<HTMLButtonElement>('random-record');
const newRun = el<HTMLButtonElement>('new-run');
const progress = el<HTMLProgressElement>('write-progress');
const format = (n: number) => Math.round(n).toLocaleString('en-US');
const cells = Array.from({ length: 240 }, () => {
  const cell = document.createElement('span');
  el('memory-grid').append(cell);
  return cell;
});
let dataset: Dataset;
let recording!: Recording;
let position = 0;
let running = false;
let paused = false;
let elapsed = 0;
const status = (text: string) => {
  el('demo-status').textContent = text;
};
function paint() {
  const frame = position ? recording.batches[position - 1] : undefined;
  const written = frame?.written || 0;
  progress.max = recording.count;
  progress.value = written;
  el('write-count').textContent =
    `${format(written)} / ${format(recording.count)} recorded writes`;
  el('write-percent').textContent =
    `${Math.floor((written / recording.count) * 100)}%`;
  cells.forEach((cell, i) =>
    cell.classList.toggle(
      'filled',
      (i + 1) / cells.length <= written / recording.count,
    ),
  );
  el('metric-count').textContent = format(written);
  el('metric-bytes').textContent = ((frame?.bytes || 0) / 1048576).toFixed(2);
  el('metric-rate').textContent = elapsed
    ? format((written / elapsed) * 1000)
    : '—';
  el('metric-errors').textContent = String(recording.errors);
  const complete = position === recording.batches.length;
  // During playback use the recorded batch percentile; at completion use the
  // exact whole-run percentile from every operation, never a scaled value.
  el('metric-p50').textContent = frame
    ? (complete ? recording.latency_ms.p50 : frame.p50_ms).toFixed(2)
    : '—';
  el('metric-p99').textContent = frame
    ? (complete ? recording.latency_ms.p99 : frame.p99_ms).toFixed(2)
    : '—';
  const trace = recording.batches.slice(0, position);
  const maximum = Math.max(1, ...trace.map((batch) => batch.client_ms));
  el('latency-trace').setAttribute(
    'points',
    trace
      .map(
        (batch, i) =>
          `${(i / Math.max(trace.length - 1, 1)) * 1000},${110 - (batch.client_ms / maximum) * 100}`,
      )
      .join(' '),
  );
  el('trace-summary').textContent =
    `${position} recorded batches · run ${recording.iteration} · ${dataset.environment.hardware.cpu}`;
  const selected = samples.value;
  samples.replaceChildren(
    ...recording.reads
      .filter((sample) => sample.index < written)
      .map((sample) => {
        const option = document.createElement('option');
        option.value = String(sample.index);
        option.textContent = `Saved record ${format(sample.index)}`;
        return option;
      }),
  );
  if ([...samples.options].some((option) => option.value === selected))
    samples.value = selected;
  read.disabled = random.disabled = samples.disabled = !written;
  el('read-range').textContent =
    'four saved responses · Live VPS lets you choose any key';
  const tab = el<HTMLAnchorElement>('reader-tab');
  tab.hidden = !complete;
  tab.href = `/demo/#replay=${recording.mode}`;
  start.textContent = complete
    ? 'Replay again →'
    : position
      ? 'Continue replay →'
      : `Replay ${format(recording.count)} writes →`;
}
function reset() {
  position = 0;
  elapsed = 0;
  recording = dataset.recordings[mode.value];
  count.value = String(recording.count);
  el<HTMLTextAreaElement>('memory-content').value = recording.content;
  el('write-preview').textContent = JSON.stringify(recording.preview, null, 2);
  el('read-output').textContent =
    'Replay the run, then recall a saved Rust response from the client cache.';
  el('read-verification').textContent =
    'Recorded responses · no new storage request';
  el('read-browser-ms').textContent = el('read-backend-ms').textContent =
    '— ms';
  el('read-browser-ms').classList.remove('timing-unresolved');
  el('read-key').textContent =
    'Exact key and recorded revision will appear here.';
  paint();
  status(
    'Recorded Mac run. Animation plays at 2×; throughput and latency use the original measured times. During playback p50/p99 describe the latest batch; completion shows the whole run.',
  );
}
async function recall() {
  const before = performance.now();
  const sample = recording.reads.find(
    (entry) => entry.index === Number(samples.value),
  );
  if (!sample) return;
  const value = JSON.parse(JSON.stringify(sample.value));
  const lookup = performance.now() - before;
  el('read-output').textContent = JSON.stringify(value, null, 2);
  const timing = el('read-browser-ms');
  timing.classList.toggle('timing-unresolved', lookup === 0);
  timing.textContent =
    lookup === 0
      ? 'Below timer resolution'
      : lookup < 0.001
        ? '<0.001 ms'
        : `${lookup.toFixed(3)} ms`;
  el('read-backend-ms').textContent = `${sample.backend_ms.toFixed(3)} ms`;
  el('read-verification').textContent = sample.verified
    ? '✓ Saved exact response · verified against the fixture during recording'
    : 'Recorded verification failed';
  el('read-key').textContent =
    `${sample.namespace}/${sample.key} · recorded revision ${sample.revision}`;
  status(
    `Record ${format(sample.index)} served from the client cache. Backend timing is from the Mac recording, not this lookup.`,
  );
}
start.disabled = true;
mode.disabled = newRun.disabled = true;
for (const id of ['memory-count', 'value-size', 'memory-content'])
  el<HTMLInputElement>(id).disabled = true;
el('record-index').hidden = true;
samples.hidden = false;
el('demo-cell-caption').textContent =
  'Recorded writes at 2× playback. No writes occur now; full-run performance numbers stay unchanged.';
start.addEventListener('click', async () => {
  if (running) return;
  if (position === recording.batches.length) reset();
  running = true;
  paused = false;
  start.disabled = newRun.disabled = mode.disabled = true;
  stop.disabled = false;
  try {
    while (position < recording.batches.length && !paused) {
      const frame = recording.batches[position];
      await new Promise((done) => setTimeout(done, frame.client_ms / 2));
      elapsed += frame.client_ms;
      position++;
      paint();
    }
    status(
      position === recording.batches.length
        ? `${format(recording.count)} actual writes recorded on ${dataset.environment.hardware.cpu}. ${format(recording.records_per_second)} records/s, zero errors. Replay complete; recall a cached saved response.`
        : 'Replay paused. Recorded statistics remain unchanged.',
    );
  } finally {
    running = false;
    start.disabled = newRun.disabled = mode.disabled = false;
    stop.disabled = true;
  }
});
stop.addEventListener('click', () => {
  paused = true;
  stop.disabled = true;
});
mode.addEventListener('change', () => {
  reset();
  history.replaceState(null, '', location.pathname);
});
newRun.addEventListener('click', reset);
read.addEventListener('click', recall);
random.addEventListener('click', () => {
  const available = [...samples.options];
  if (!available.length) return;
  samples.value =
    available[
      crypto.getRandomValues(new Uint32Array(1))[0] % available.length
    ].value;
  void recall();
});
el('clear-context').addEventListener('click', () => {
  el<HTMLTextAreaElement>('memory-content').value = '';
  el('write-preview').textContent =
    'Writer preview cleared. The recorded responses remain in the client cache.';
  el('read-output').textContent =
    'Recall a saved response. This replay illustrates retrieval; Live VPS tests storage independent of this browser.';
  el('read-browser-ms').textContent = el('read-backend-ms').textContent =
    '— ms';
  el('read-browser-ms').classList.remove('timing-unresolved');
  el('read-verification').textContent =
    'Preview cleared · recorded responses still cached';
  status(
    'Only the preview was cleared. Replay data remains cached; use Live VPS for a real independent storage round trip.',
  );
});
async function loadRecording() {
  try {
    const response = await fetch('/recordings/mac/replay.json', {
      cache: 'force-cache',
    });
    if (!response.ok) throw new Error('Recording unavailable. Try Live VPS.');
    dataset = await response.json();
    const restored = new URLSearchParams(location.hash.slice(1)).get('replay');
    if (restored === 'cache' || restored === 'durable') mode.value = restored;
    reset();
    start.disabled = false;
    mode.disabled = newRun.disabled = false;
    if (restored) {
      position = recording.batches.length;
      elapsed = recording.elapsed_ms;
      paint();
      status(
        'Recorded reader restored. Recall a saved response from this browser’s copy of the recording.',
      );
    }
  } catch (error) {
    status(
      error instanceof Error
        ? error.message
        : 'Recording unavailable. Try Live VPS.',
    );
  }
}
void loadRecording();
