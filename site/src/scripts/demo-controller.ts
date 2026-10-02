const selector = document.getElementById('demo-source') as HTMLSelectElement;
const live =
  new URLSearchParams(location.search).get('source') === 'live' ||
  /^[a-f0-9]{48}$/.test(
    new URLSearchParams(location.hash.slice(1)).get('run') || '',
  );
selector.value = live ? 'live' : 'recorded';
selector.addEventListener('change', () => {
  location.assign(selector.value === 'live' ? '/demo/?source=live' : '/demo/');
});
if (live) {
  document.getElementById('writer-path')!.textContent = 'PUT → STORAGE';
  document.getElementById('reader-path')!.textContent = 'STORAGE → GET';
  document.getElementById('demo-source-label')!.textContent =
    'Live storage / real Rust engine';
  document.getElementById('demo-path')!.textContent =
    'CLOUDFLARE EDGE → INSTANTKV';
  document.getElementById('demo-cell-caption')!.textContent =
    'Each lit cell represents records the server has saved.';
  document.getElementById('read-client-label')!.textContent =
    'Browser round-trip';
  document.getElementById('read-backend-label')!.textContent =
    'Backend HTTP read';
  document.getElementById('trace-label')!.textContent =
    'Browser batch round-trip / live trace';
  document.getElementById('error-unit')!.textContent = 'browser API requests';
  document.getElementById('demo-status')!.textContent =
    'Live VPS mode. Choose a workload and store your first memories.';
  void import('./demo').catch(() => {
    document.getElementById('demo-status')!.textContent =
      'Demo could not load. Reload this page.';
  });
} else {
  void import('./replay').catch(() => {
    document.getElementById('demo-status')!.textContent =
      'Recording could not load. Try Live VPS.';
  });
}
