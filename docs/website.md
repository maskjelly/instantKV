# Website and documentation deployment

The public site introduces instantKV, hosts the setup/feature/contributor docs
and publishes reproducible benchmarks. The Rust memory service remains a
separately self-hosted process. Managed hosting is in development.

## Stack and boundaries

Astro + TypeScript builds static HTML. Cloudflare Workers Static Assets serves
the files; no server-side JavaScript or site database is needed. Pagefind generates
browser-local search. The only client scripts provide search, code copying and
benchmark chart controls. Fonts and images are served locally.

This follows [Cloudflare's static Astro deployment guide](https://developers.cloudflare.com/workers/framework-guides/web-apps/astro/).
[Static asset requests are free and unlimited under current Cloudflare billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/);
that applies to the website and does not mean memory-node infrastructure is free.
We keep redb on real persistent storage; the docs site does not route agent writes
to Cloudflare KV or pretend an eventually consistent cache supplies its transactions.

## One documentation source

`site/src/lib/docs.ts` defines navigation and descriptions. Astro's collection
reads `docs/*.md`, `CONTRIBUTING.md`, `SECURITY.md` and `CHANGELOG.md` directly.
Edit those Markdown files rather than copying prose into a second docs tree.
The build rewrites relative repository links for the website, copies artwork,
examples and all benchmark JSON, and generates `llms.txt`/`llms-full.txt`.

The benchmark page computes medians and totals from the 15 checked-in reports.
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
npm run deploy:domain   # instantkv.com and www.instantkv.com
```

`deploy` runs type/content checks, builds, verifies and uploads. The production
Wrangler environment attaches two Custom Domains. Cloudflare creates their DNS
records and certificates; preserve unrelated email/DNS records. If an existing
CNAME conflicts, inspect it before changing anything. A pending zone must activate
before Custom Domains can be used. See [official domain setup](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).

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
route after publishing. Confirm search works under the site's Content Security
Policy and that the domain serves the new build. There is no website user-data
migration. To roll back, check out the last reviewed site commit and redeploy its
static build. Record the deployed commit/version and verification result in
[checkpoints](checkpoints.md).
