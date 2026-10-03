# Website

The public site explains the local-first source MVP and publishes benchmark evidence.
It uses Astro, plain CSS, self-hosted Geist and static Cloudflare Worker assets.
There is no public memory demo. Storage examples run on the reader's own device.

## Build and verify

```sh
cd site
npm ci
npm run check
npm test
npm run build
npm run verify
```

The build copies current benchmark JSON, ranking files, verification receipts,
examples and documentation into static assets. It generates `llms.txt`,
`llms-full.txt`, a sitemap and a Pagefind search index.

Chart values come from committed reports in `src/lib/evidence.ts` and
`src/lib/benchmarks.ts`. Retrieval scores and synthetic latency have different
workloads. Keep their labels and comparison limits visible.

## Publish

```sh
npm run deploy:domain
```

The Worker serves static assets. Old demo page links redirect to quick start.
Requests under `/api/demo` return HTTP 410 and cannot reach a memory backend.
The deployment has no demo VPC, rate-limit or required secret binding.
Existing backend resources are not removed by this website change.

## Visual assets

Three generated editorial photos illustrate local devices and storage. They do
not show benchmark hardware or prove phone support. See the asset manifest in
[docs/assets/imagery.md](assets/imagery.md). Quantitative charts use report data.
Keep the minimal layout, local font, keyboard controls and reduced-motion support.
