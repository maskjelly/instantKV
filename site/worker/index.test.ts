import assert from 'node:assert/strict';
import test from 'node:test';
import worker from './index.ts';

test('retired demo routes cannot reach assets or a backend', async () => {
  let calls = 0;
  const env = {
    ASSETS: {
      fetch: async () => {
        calls++;
        return new Response('asset');
      },
    },
  } as unknown as Env;
  for (const method of ['GET', 'POST', 'DELETE']) {
    for (const path of [
      '/api/demo',
      '/api/demo/remember',
      '/api/demo/arbitrary',
    ]) {
      const response = await worker.fetch(
        new Request('https://instantkv.com' + path, { method }),
        env,
      );
      assert.equal(response.status, 410);
      assert.equal(response.headers.get('cache-control'), 'no-store');
    }
  }
  assert.equal(calls, 0);
});

test('ordinary requests preserve asset responses and request identity', async () => {
  const request = new Request('https://instantkv.com/benchmarks/');
  const expected = new Response('benchmark page', { status: 200 });
  const env = {
    ASSETS: {
      fetch: async (received: Request) => {
        assert.equal(received, request);
        return expected;
      },
    },
  } as unknown as Env;
  assert.equal(await worker.fetch(request, env), expected);
});
