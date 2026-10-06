# Website

The site is the front door to an installable local service. Help readers understand
the tool, install it, connect a runtime and operate their own node.
Use source status, working commands and inspectable evidence. Keep the README brief.

## Design and content contract

- Lead with source installation and the local service defaults.
- Explain saved records, interfaces and operating limits before benchmark scores.
- Keep the app's responsibility clear: fact extraction and context assembly belong to the runtime.
- Label the memory MVP as unreleased. Older published archives lack its tools.
- Link each measurement to its workload, process scope and raw evidence.
- Put backup, configuration, security and contribution paths within reach.
- Keep adoption counts private. [Local reporting and counting limits](install-metrics.md).

The visual direction is a restrained technical reference site: self-hosted Geist,
one blue link accent, short lines and generous section spacing. Native Astro and
plain CSS fit the static content. Light and dark modes follow the system setting.
Interaction motion is limited to feedback. Device concept photos do not help a
reader install or operate the service, so they are absent from the landing page.
Design variation is 4/10, motion is 2/10 and density is 5/10: installation and
reference reading set the hierarchy; interface feedback is the only motion.

## Live-site audit and redesign plan

Inspected the live homepage, quick start, documentation index, research article
and benchmarks on 6 October 2026. Their responses and headings were available.
The previous site used white surfaces, Geist, a small wordmark and device imagery.
Navigation led to Docs, Research, Benchmarks and GitHub. Installation appeared
after prominent retrieval scores and several narrative sections.

The information was useful, but its order weakened the installation path.
The stylesheet also combined several redesigns in one 2,848-line file.
The replacement keeps published routes, nav labels, headings used by links,
raw reports, local search, the wordmark and canonical metadata.

| Area | Change | Acceptance |
| --- | --- | --- |
| Homepage | Install first; real save/recall example; boundaries before evidence | Exact source command, release warning, loopback and data path visible |
| README | One installation path and short current contract | Commands match the site and source guides |
| Docs | Task shortcuts and readable guide navigation | Desktop sidebar; mobile menu; all guide links resolve |
| Evidence | Shared site tokens; separate retrieval, QA and storage labels | Raw report hashes and scores unchanged; controls work |
| Styles | Shared base plus page/component files | No layered landing-page overrides; mobile and dark mode checked |
| Adoption | Private local maintainer ledger | No public count; no installed-service reporting; downloads labelled honestly |

## Source map

- `site/src/layouts/Base.astro`: metadata, local fonts and copy controls.
- `site/src/components/{Header,Footer}.astro`: shared navigation.
- `site/src/pages/index.astro`: installation and service overview.
- `site/src/pages/docs/`: task index and guides from repository Markdown.
- `site/src/lib/docs.ts`: route registry and guide groups.
- `site/src/lib/{evidence,benchmarks}.ts`: report-backed chart/table data.
- `site/src/styles/`: `global.css`, `home.css`, `docs.css`, `diagrams.css`, `evidence.css`, `benchmarks.css`.
- `site/worker/`: static assets and the retired demo response.
- `site/scripts/verify.mjs`: built routes, links, assets, schemas and evidence checks.

Guide content has one Markdown source. The build publishes report files,
examples, per-guide Markdown, `llms.txt`, `llms-full.txt`, a sitemap and a Pagefind search index.
[Search and agent discovery](discovery.md) defines indexing, export and claim rules.
Resource exports preserve their process scopes. Model QA keeps its own settings,
failures and confidence interval. Keep these distinctions visible.

## Build and verify

```sh
cd site
npm ci
npm audit --audit-level=high
../scripts/check.sh --site
```

Before publication, inspect the built site at desktop, tablet and 320-pixel mobile
widths. Check both themes, keyboard focus, menu links, copy controls, search results,
empty results, chart selection, horizontal tables and existing anchors.
The static verifier cannot prove visual quality or external-link availability.
Run the full repository verifier after shared script or dependency changes.

The site pins Miniflare's Sharp dependency to 0.35.5 through an npm override.
Wrangler 4.145.0 otherwise installs Sharp 0.35.4, affected by
[the upstream librsvg advisory](https://github.com/advisories/GHSA-wq5f-xc86-pv6w).
Keep the override until the pinned upstream dependency includes a patched version.
Check a clean npm install, audit, site build and local Worker before removing it.

## Publish

```sh
cd site
npm run deploy:domain
```

Deployment is separate from pushing source. Website CI builds and checks the site;
it does not publish it. The Worker serves static assets. Old demo pages redirect
to quick start. Requests under `/api/demo` return HTTP 410.
There is no hosted memory backend or installation-reporting endpoint in this site.

The checked-in site loads scripts, fonts and search from its own origin and contains
no visitor analytics script. Cloudflare domain settings can inject a Web Analytics
beacon after deployment; inspect public responses as well as build output.
The source CSP blocks that external script. Remove automatic injection in the
Cloudflare dashboard to avoid a blocked request.
Private download snapshots are never copied into static
assets. Retained historical artwork has provenance in [the asset guide](assets/README.md).
