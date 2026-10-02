# Website and documentation deployment

The site provides setup guides, product details and benchmark evidence.
The memory service remains a local process. Storage and retrieval do not depend on the hosted site or demo.

## Stack and boundaries

Astro and TypeScript build static HTML. Cloudflare Workers Static Assets serves the files.
A small Worker forwards `/api/demo/*` to the isolated [live demo](live-demo.md).
Pagefind provides browser-local search. Local scripts handle search, code copying and benchmark controls.
Fonts and images are served locally.

Cloudflare zone-level Web Analytics adds a beacon.
The Content Security Policy permits its specific script and collection hosts alongside local code.

The setup follows [Cloudflare's Astro deployment guide](https://developers.cloudflare.com/workers/framework-guides/web-apps/astro/).
[Static asset billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/) applies to the website, not the memory-node infrastructure.
The demo uses real instantKV transactions and redb on persistent VPS storage.

## Website design

The website uses white surfaces, neutral borders, a black split-K mark and locally served Geist.
The homepage shows local memory, a CLI example, measured resource use and installation commands.
It has no moving banner or decorative grid.

Demo, benchmark and documentation pages use the same design.
Guides are grouped by task. Technical diagrams expand on request.
Search, code copying, replay, live storage and benchmark controls remain available.

Theme settings and responsive layout use `site/src/styles/global.css`.
Diagrams use SVG/HTML components in `site/src/components/diagrams/`.
The [mark](assets/blueprint-mark.svg) and [social preview](assets/blueprint-social.svg) are editable SVG.
The preview also has a 1200 × 630 PNG export.
[Font sources and license](assets/fonts/README.md).

The references were [Vercel](https://vercel.com/),
[Cloudflare](https://www.cloudflare.com/) and [Google Cloud](https://cloud.google.com/):
clear navigation, restrained typography and concrete product explanations.
The layout and assets are original. Measurements stay tied to their workloads.

## One documentation source

`site/src/lib/docs.ts` defines navigation and descriptions.
Astro reads `docs/*.md`, `CONTRIBUTING.md`, `SECURITY.md` and `CHANGELOG.md` directly.

Edit those Markdown files to update the website documentation.

The build rewrites relative links, copies assets and generates `llms.txt` and `llms-full.txt`.

The homepage and benchmark page compute memory figures from the 2026-10-03 raw report.
Earlier Mac recordings and 15 VPS reports remain separate.
Each dataset retains its source revision, transport, hardware and load conditions.
Replace a dataset only after a complete new measurement and verification.

## Local development

Node 22.12+ and npm; the lockfile pins dependencies:

```sh
cd site
npm ci
npm run dev
```

`dev` previews content and styles. To verify built search and Cloudflare routing,
build first and run the actual static-asset server:

```sh
npm run check
npm test
npm run build
npm run verify
npm run preview
```

The verifier tests rendered links, anchors, assets, reports and machine-readable docs.
Browser checks must cover desktop/mobile layout, code copying, search, chart controls, reduced motion and the 404 page.

## Deploy to Cloudflare

Authenticate with `npx wrangler login` in your terminal. The deployment account
must own the active `instantkv.com` zone. Never commit access tokens.

```sh
cd site
npm run deploy          # workers.dev, before domain activation
npm run deploy:domain   # instantkv.com
```

`deploy` runs content/type checks, builds, verifies and uploads.
The production environment attaches the apex Custom Domain at `instantkv.com`.
Cloudflare creates the required DNS records and certificates.
The zone must be active.
The optional `www` hostname has an externally managed conflict and is not configured.

Preserve unrelated DNS and email records.
Inspect conflicting records with their owner before changing them.
[Official domain setup](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).

Workers Builds can provide optional continuous deployment. Its settings are:

| Setting           | Value                                              |
| ----------------- | -------------------------------------------------- |
| Root directory    | `site`                                             |
| Production branch | `main`                                             |
| Build command     | `npm run check && npm run build && npm run verify` |
| Deploy command    | `npx wrangler deploy --env production`             |

The GitHub website workflow verifies pushes and pull requests. It does not deploy pull-request code with production credentials.

Manual Wrangler deployment and Workers Builds use separate account permissions.
Wrangler OAuth can publish the site; the Builds API needs additional user-token permissions.
Until Builds is configured, use `npm run deploy:domain` from a reviewed checkout.
Do not copy expiring interactive OAuth tokens into GitHub secrets.

## Verification and rollback

Browser search and `llms-full.txt` include the memory guide, performance plan and roadmap.
`llms.txt` describes the four tools, unreleased status and measured/planned boundaries.
The Ollama example and memory schemas are available under `/examples/`.

1. Verify HTTPS on `/`, `/docs/quickstart/`, `/benchmarks/` and `/llms.txt`.
2. Verify the 404 response for a missing route.
3. Test search, copying and desktop/mobile layout.
4. Run cache and durable live-demo writes.
5. Verify exact recall in an independent tab.
6. Compare deployed report/schema files with the reviewed build.

The static site has no user-data migration.
To roll back, deploy the last reviewed site commit.
Record the commit, deployment version and results in [verification history](checkpoints.md).
