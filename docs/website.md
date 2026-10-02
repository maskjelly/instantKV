# Website and documentation deployment

The public site introduces instantKV, hosts the setup/feature/contributor docs
and publishes reproducible benchmarks. The Rust memory service remains a
separately self-hosted process. Managed hosting is in development.

## Stack and boundaries

Astro + TypeScript builds static HTML. Cloudflare Workers Static Assets serves
the files. A small Worker proxies only `/api/demo/*` to the isolated Rust-backed
[live demo](live-demo.md); documentation needs no database. Pagefind generates
browser-local search. Application scripts provide search, code copying,
benchmark chart controls and announcement pause/play. Fonts and images are
served locally. Cloudflare's existing zone-level Web Analytics injects its beacon;
the CSP permits only its specific script/collection hosts alongside local code.

This follows [Cloudflare's static Astro deployment guide](https://developers.cloudflare.com/workers/framework-guides/web-apps/astro/).
[Static asset requests are free and unlimited under current Cloudflare billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/);
that applies to the website and does not mean memory-node infrastructure is free.
The demo's Rust service runs redb on persistent VPS storage. Its records and
transactions use instantKV's storage engine.

## Website design

The website uses a white technical blueprint theme. Blue ink, fine rules,
square controls and graph-paper diagrams give it the feel of an early product
sketch. The split-K mark keeps its original shape in a flat blue variant.
There are no 3D objects, shader effects or background animations.

The homepage explains the service, shows measured performance, gives a working
install command and diagrams shared knowledge with private worker namespaces.
The same typography and controls carry through the demo, benchmarks and guides.
This is a self-hosted product page: install, read the docs, try the demo.
Managed hosting stays a labeled future offering.

Theme tokens live in `site/src/styles/global.css`. Technical diagrams use native
SVG components in `site/src/components/diagrams/`; the homepage request path is
`MemoryBlueprint.astro`. The shared/private memory diagram uses responsive
HTML/CSS, so its labels wrap at readable sizes on mobile. The dashed server
boundary contains shared knowledge, two private namespaces and the scoped API;
cloud workers sit outside it. [Logo](assets/blueprint-mark.svg) and [social image source](assets/blueprint-social.svg)
are editable SVG. The social preview also has a 1200 × 630 PNG export.

[Redis](https://redis.io/) and [Valkey](https://valkey.io/) were reviewed for clear
product explanations and direct installation/documentation paths. The artwork
and layout are original. Benchmark claims stay tied to their actual workloads.

## One documentation source

`site/src/lib/docs.ts` defines navigation and descriptions. Astro's collection
reads `docs/*.md`, `CONTRIBUTING.md`, `SECURITY.md` and `CHANGELOG.md` directly.
Edit those Markdown files; you don't need to maintain a second copy for the site.
The build rewrites relative repository links for the website, copies artwork,
examples and all benchmark JSON, and generates `llms.txt`/`llms-full.txt`.

The benchmark page computes medians and totals from the 15 VPS reports and shows
the median-throughput recordings from six actual Mac runs separately.
Keep their recorded source revision, transport, hardware and host load visible.
Only replace a dataset after collecting and verifying a new complete set.

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

The verifier checks every rendered local link/anchor/asset, the raw reports and
machine-readable docs. Browser QA should cover desktop/mobile, code copying,
search, chart controls, reduced motion and the custom 404 response.

## Deploy to Cloudflare

Authenticate with `npx wrangler login` in your terminal. The deployment account
must own the active `instantkv.com` zone. Never commit access tokens.

```sh
cd site
npm run deploy          # workers.dev, before domain activation
npm run deploy:domain   # instantkv.com
```

`deploy` runs type/content checks, builds, verifies and uploads. The production
Wrangler environment attaches the apex Custom Domain. Cloudflare creates its DNS
records and certificates; preserve unrelated email/DNS records. If an existing
CNAME conflicts, inspect it before changing anything. A pending zone must activate
before Custom Domains can be used. The optional `www` hostname has an externally
managed DNS conflict and is not configured for this Worker. Keep the canonical
site at `instantkv.com`; inspect that record with its owner before changing it.
See [official domain setup](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).

For continuous deployment, connect this repository to **Workers Builds** with
root directory `site`, build command `npm run check && npm run build && npm run verify`
and deploy command `npx wrangler deploy --env production`. Use main as production.
The checked-in GitHub site workflow runs these checks on pushes and pull requests;
it does not publish untrusted PR code with deployment credentials.

Continuous deployment is an optional account integration, separate from a manual
Wrangler publication. A Wrangler OAuth login can publish the website but the
Builds configuration API requires additional user-token permissions. Connect
Workers Builds in the dashboard if those permissions are unavailable; until then
run `npm run deploy:domain` from a reviewed checkout. Do not store an expiring
interactive OAuth token in GitHub secrets.

## Verification and rollback

Verify HTTPS at `/`, `/docs/quickstart/`, `/benchmarks/`, `/llms.txt` and a missing
route after publishing. Run the live demo in both cache and durable modes,
including cross-tab recall. Confirm search works under the site's Content Security
Policy and that the domain serves the new build. There is no website user-data
migration. To roll back, check out the last reviewed site commit and redeploy its
static build. Record the deployed commit/version and verification result in
[checkpoints](checkpoints.md).
