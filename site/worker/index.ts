export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const path = new URL(request.url).pathname;
    if (path === '/api/demo' || path.startsWith('/api/demo/')) {
      return new Response(
        'The public demo has been retired. See /docs/quickstart/.',
        {
          status: 410,
          headers: {
            'Content-Type': 'text/plain; charset=utf-8',
            'Cache-Control': 'no-store',
          },
        },
      );
    }
    return env.ASSETS.fetch(request);
  },
} satisfies ExportedHandler<Env>;
