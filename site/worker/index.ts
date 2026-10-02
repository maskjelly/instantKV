export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/api/demo/'))
      return env.ASSETS.fetch(request);
    const reply = (status: number, error: string) =>
      Response.json(
        { error },
        {
          status,
          headers: {
            'cache-control': 'no-store',
            'x-content-type-options': 'nosniff',
          },
        },
      );
    if (request.method !== 'POST') return reply(405, 'POST required');
    if (
      ![
        '/api/demo/session',
        '/api/demo/write',
        '/api/demo/read',
        '/api/demo/status',
        '/api/demo/query',
        '/api/demo/forget',
      ].includes(url.pathname)
    )
      return reply(404, 'Unknown demo operation');
    if (request.headers.get('origin') !== url.origin)
      return reply(403, 'Open the demo on this website');
    if (
      !(
        await env.DEMO_RATE_LIMIT.limit({
          key: request.headers.get('cf-connecting-ip') || 'anonymous',
        })
      ).success
    )
      return reply(429, 'Demo request limit reached. Try again in a minute.');
    if (!env.DEMO_GATEWAY_TOKEN)
      return reply(503, 'Demo is temporarily unavailable');
    if (!request.headers.get('content-type')?.startsWith('application/json'))
      return reply(415, 'JSON required');
    const reader = request.body?.getReader();
    if (!reader) return reply(400, 'Request body required');
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 8192) {
        await reader.cancel();
        return reply(413, 'Request too large');
      }
      chunks.push(value);
    }
    const body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      body.set(chunk, offset);
      offset += chunk.byteLength;
    }
    try {
      const response = await env.DEMO_BACKEND.fetch(
        `${env.DEMO_ORIGIN}${url.pathname.slice('/api/demo'.length)}`,
        {
          method: 'POST',
          body,
          headers: {
            authorization: `Bearer ${env.DEMO_GATEWAY_TOKEN}`,
            'content-type': 'application/json',
          },
          redirect: 'manual',
          signal: AbortSignal.timeout(25000),
        },
      );
      if (response.status >= 300 && response.status < 400) {
        await response.body?.cancel();
        return reply(
          503,
          'Demo origin must respond directly without a redirect',
        );
      }
      if (!response.headers.get('content-type')?.includes('application/json')) {
        await response.body?.cancel();
        return reply(
          503,
          'Demo storage returned an invalid response. Retry shortly.',
        );
      }
      return new Response(response.body, {
        status: response.status,
        headers: {
          'content-type': 'application/json',
          'cache-control': 'no-store',
          'x-content-type-options': 'nosniff',
        },
      });
    } catch (error) {
      console.error(
        JSON.stringify({
          event: 'demo_origin_failed',
          message:
            error instanceof Error ? error.message : 'upstream request failed',
        }),
      );
      return reply(
        503,
        'Demo storage is temporarily unavailable. Retry shortly.',
      );
    }
  },
} satisfies ExportedHandler<Env>;
