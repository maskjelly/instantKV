import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from './index.ts';

function environment(allowed = true) {
  return {
    DEMO_ORIGIN: 'http://instantkv-demo.internal',
    DEMO_BACKEND: {
      fetch: async (_url: RequestInfo | URL, _options?: RequestInit) =>
        Response.json({}),
      connect: () => {
        throw new Error('Only HTTP requests are used');
      },
    },
    DEMO_GATEWAY_TOKEN: 'server-only-key',
    DEMO_RATE_LIMIT: { limit: async () => ({ success: allowed }) },
    ASSETS: {
      fetch: async () => new Response('static assets'),
      connect: () => {
        throw new Error('Not used by this Worker');
      },
    },
  } satisfies Env;
}
function request(path = 'read', extra: RequestInit = {}) {
  return new Request(`https://instantkv.com/api/demo/${path}`, {
    method: 'POST',
    headers: {
      origin: 'https://instantkv.com',
      'content-type': 'application/json',
    },
    body: '{"id":"test","index":0}',
    ...extra,
  });
}
test('static assets bypass demo; methods, origin, routes, size and rate limits reject unsafe requests', async () => {
  assert.equal(
    await (
      await worker.fetch(
        new Request('https://instantkv.com/docs/'),
        environment(),
      )
    ).text(),
    'static assets',
  );
  assert.equal(
    (await worker.fetch(request('arbitrary'), environment())).status,
    404,
  );
  assert.equal(
    (
      await worker.fetch(
        request('read', { method: 'GET', body: undefined }),
        environment(),
      )
    ).status,
    405,
  );
  assert.equal(
    (
      await worker.fetch(
        request('read', {
          headers: {
            origin: 'https://attacker.example',
            'content-type': 'application/json',
          },
        }),
        environment(),
      )
    ).status,
    403,
  );
  assert.equal(
    (await worker.fetch(request('read'), environment(false))).status,
    429,
  );
  assert.equal(
    (
      await worker.fetch(
        request('read', { body: 'x'.repeat(8193) }),
        environment(),
      )
    ).status,
    413,
  );
});

test('origin redirects are refused before credentials can leave the configured backend', async (t) => {
  let calls = 0;
  const env = environment();
  env.DEMO_BACKEND.fetch = async (_url, options) => {
    calls++;
    assert.equal(options?.redirect, 'manual');
    return new Response(null, {
      status: 302,
      headers: { location: 'https://another-origin.example' },
    });
  };
  assert.equal((await worker.fetch(request(), env)).status, 503);
  assert.equal(calls, 1);
});
test('proxy forwards only the fixed origin, keeps credentials server-side and never caches reads', async (t) => {
  const env = environment();
  env.DEMO_BACKEND.fetch = async (url, options) => {
    assert.equal(url, 'http://instantkv-demo.internal/read');
    assert.equal(
      new Headers(options?.headers).get('authorization'),
      'Bearer server-only-key',
    );
    assert.equal(options?.redirect, 'manual');
    return Response.json({ value: 'stored context', backend_ms: 1.2 });
  };
  const response = await worker.fetch(request(), env);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(response.status, 200);
  assert(!JSON.stringify(await response.json()).includes('server-only-key'));
});
