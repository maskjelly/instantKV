# Search and agent discovery

Audience: maintainers. Updated 8 October 2026.
Keep instantKV easy to find, understand, install and cite.
The current positioning is **open-source local AI memory for agents**.
The structured-memory source MVP is unreleased.

## What the site publishes

| Surface | Contract |
| --- | --- |
| HTML | Static readable content, one page heading, description and canonical URL |
| Project identity | JSON-LD: WebSite, SoftwareSourceCode, WebPage and breadcrumbs; docs also use TechArticle |
| Guides | One repository source; HTML plus a linked Markdown copy at `/docs/<slug>/index.md` |
| Agent entry | `/llms.txt`: concise setup, limits and links to selected Markdown guides |
| Complete reference | `/llms-full.txt`: all published guides with absolute resource links |
| Sitemap | Indexable HTML only; excludes search, 404, verification history and the distributed proposal |
| Robots | Public content allowed; sitemap advertised; no change to training policy |
| Evidence | Raw reports, conditions and comparison limits stay public and unchanged |

The source entity identifies the MIT-licensed repository and Rust implementation.
It does not contain fabricated ratings, install counts or a purchasable offer.
Existing guide URLs stay stable. History and proposals remain accessible through
navigation, with noindex to keep them out of current-feature search results.

## Build and publication

The registry in `site/src/lib/docs.ts` owns guide routes.
`site/src/lib/discovery.ts` owns project identity and indexing exclusions.
`site/src/lib/repository-links.mjs` resolves links for HTML and Markdown.
`site/scripts/agent-content.mjs` generates agent exports.
Update the source guide when behavior changes. Do not hand-edit generated files.
The generated `/llms.txt` points coding agents to the roadmap, project plan,
repository rules, contributor checks and `AGENTS.md`. Keep those links working.
An agent can use one acceptance check as its task, make a focused change, run
the relevant checks and report remaining limits. Discovery text does not grant
permission to publish a release or run model evaluations.

Run:

```sh
./scripts/check.sh --site
```

The checks reject invalid structured data, broken export links, executable inline
scripts, missing canonical metadata and incorrect sitemap inclusion.
They test Markdown links, reference definitions, code preservation and JSON-LD
escaping. They do not prove search ranking or model citation quality.

Use the [website publication procedure](website.md#publish).
After deployment, fetch the homepage, robots, sitemap, agent index and MCP guide
with ordinary, Googlebot and OAI-SearchBot user agents. Confirm HTTP 200, correct
content types and no login or challenge page. A spoofed user agent is only a
smoke test; check verified crawler traffic and Cloudflare controls separately.
The origin's robots file cannot override an edge firewall or crawler block.

Cloudflare Browser Integrity Check can reject generic HTTP clients, including
Python's default user agent. Use an identified client user agent for diagnostics.
For public read-only documentation, an owner can make a narrow configuration-rule
exception for Browser Integrity Check while retaining other protections.
Disable automatic Web Analytics injection for this site in the dashboard or
with a configuration rule using disable_rum. The source CSP blocks its external
beacon. These settings need zone configuration access; Workers deployment access
alone is insufficient. See [Cloudflare configuration settings](https://developers.cloudflare.com/rules/configuration-rules/settings/).

An owner can fix both settings without sharing a token:

1. Open instantkv.com in Cloudflare, then Rules → Create rule → Configuration Rule.
2. Name it "Public documentation reads".
3. Use the expression below.
4. Set Browser Integrity Check to Off and Disable Real User Monitoring to On.
5. Deploy, then repeat the public HTTP checks.

```text
http.host eq "instantkv.com" and http.request.method in {"GET" "HEAD"}
```

This domain serves public static content and a retired-demo response, not the
installed memory API. The exception applies only to reads on this hostname.
Other protections and methods retain their existing settings.
For API management, create a custom token with Zone → Config Rules → Edit,
restricted to instantkv.com. The API calls this permission Config Settings Write.
Keep it outside the checkout. Do not send tokens in chat.

Use an authenticated owner account to verify `instantkv.com` in Google Search
Console and Bing Webmaster Tools. Submit `/sitemap-index.xml`. Inspect the home,
quick-start and MCP pages. Record selected canonical URLs and indexing failures.
Repository access does not grant access to those accounts.

## Measure useful discovery

Keep a private dated log outside the repository. Review it monthly.

| Question | Evidence |
| --- | --- |
| Can crawlers reach the guides? | HTTP checks plus verified crawler requests and edge failures |
| Are the right pages indexed? | Search Console coverage and URL inspection; record exclusions |
| Are people finding the tool? | Impressions, clicks and query groups from webmaster reports |
| Can an agent install it correctly? | Start at llms.txt; follow source setup and MCP guide in a fresh directory |
| Are claims quoted correctly? | Check source/release status, retrieval versus QA, and local-runtime limits |
| Is adoption growing? | [Private download ledger](install-metrics.md); source installs and verified installs remain unknown |

Useful query groups include local AI memory, local agent memory, MCP memory server,
Rust agent memory, BM25 agent retrieval and durable agent checkpoints.
Track page/query pairs. Do not create thin pages for every keyword variation.
For citation checks, record the model, date, exact prompt and cited URL.
Small manual samples are observations, not an engine benchmark.

## Earn the next claim

Search metadata makes the project legible. It does not make it SOTA.
Current reports show competitive retrieval, with no statistically significant
retrieval win established. Preserve [evaluation boundaries](evaluation-policy.md).

1. Publish a tested memory-MVP release with matching binaries and schemas.
2. Verify fresh installation and explicit agent continuation on supported hosts.
3. Publish useful integration examples backed by actual tool calls.
4. Complete fair, frozen comparisons before making superiority claims.
5. Record outside adoption, issue resolution and contributor experience.

An open-source staple needs repeatable installation, a stable contract and
maintained integrations. Keyword repetition cannot replace those.

## Search guidance and limits

Google says normal SEO applies to AI search. Its systems do not use llms.txt
to improve visibility or ranking. Markdown exports serve agents and other readers.
Schema.org describes the source-code entity; this is not a claim of Google
software-app rich-result eligibility.

- [Google: optimizing for generative AI search](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide?version=published)
- [llms.txt proposal](https://llmstxt.org/): agent index and Markdown discovery links
- [Schema.org SoftwareSourceCode](https://schema.org/SoftwareSourceCode)

Ranking, indexing and inclusion are controlled by search providers.
Revert discovery tooling and metadata together if publication checks fail.
The memory engine and database format are unchanged by this work.
