# Website and documentation deployment

The public site introduces instantKV, hosts the setup/feature/contributor docs
and publishes reproducible benchmarks. The Rust memory service remains a
local-first process. The hosted website/demo is optional; local storage and
recall do not depend on it.

## Stack and boundaries

Astro + TypeScript builds static HTML. Cloudflare Workers Static Assets serves
the files. A small Worker proxies only `/api/demo/*` to the isolated Rust-backed
[live demo](live-demo.md); documentation needs no database. Pagefind generates
browser-local search. Application scripts provide search, code copying,
benchmark chart controls. Fonts and images are
served locally. Cloudflare's existing zone-level Web Analytics injects its beacon;
the CSP permits only its specific script/collection hosts alongside local code.

This follows [Cloudflare's static Astro deployment guide](https://developers.cloudflare.com/workers/framework-guides/web-apps/astro/).
[Static asset requests are free and unlimited under current Cloudflare billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/);
that applies to the website and does not mean memory-node infrastructure is free.
The demo's Rust service runs redb on persistent VPS storage. Its records and
transactions use instantKV's storage engine.

## Website design

The website uses white surfaces, neutral borders and locally served Geist
variable typography. The split-K mark is black. The homepage has a short
local-first explanation, a real CLI save/recall example, measured footprint and
one installation path. It has no moving banner, decorative grid or hero diagram.

The same type and surface rules apply to the demo, benchmarks and documentation.
Docs are grouped by task, and technical diagrams expand on request. Search,
code copying, recorded/live demo modes and benchmark controls remain functional.

Theme tokens and responsive layout live in `site/src/styles/global.css`.
Technical diagrams use native SVG/HTML components in
`site/src/components/diagrams/`. The [mark](assets/blueprint-mark.svg) and
[social preview](assets/blueprint-social.svg) are editable SVG; the latter also
has a 1200 × 630 PNG export. Font source and license are in
[the font directory](assets/fonts/README.md).

The references were [Vercel](https://vercel.com/),
[Cloudflare](https://www.cloudflare.com/) and [Google Cloud](https://cloud.google.com/):
clear navigation, restrained typography and concrete product explanations.
The layout and assets are original. Measurements stay tied to their workloads.

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

The homepage and benchmark page read the new structured-memory report directly.
The memory guide, performance plan and roadmap are included in browser search and
`llms-full.txt`. `llms.txt` names the four tools, states that the MVP is unreleased
and separates Mac evidence from planned native mobile work. The optional Ollama
example and generated memory schemas are downloadable under `/examples/`.

Verify HTTPS at `/`, `/docs/quickstart/`, `/benchmarks/`, `/llms.txt` and a missing
route after publishing. Run the live demo in both cache and durable modes,
including cross-tab recall. Confirm search works under the site's Content Security
Policy and that the domain serves the new build. There is no website user-data
migration. To roll back, check out the last reviewed site commit and redeploy its
static build. Record the deployed commit/version and verification result in
[checkpoints](checkpoints.md).
