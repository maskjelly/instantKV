export const repository = 'https://github.com/maskjelly/instantKV';
export const docs = [
  {
    slug: 'memory-mvp',
    title: 'Memory API & local models',
    group: 'Start here',
    source: 'docs/memory-mvp.md',
    description:
      'Remember, recall, browse and forget. Topic/tag/time retrieval, bounded keywords and a local-model example.',
  },
  {
    slug: 'performance',
    title: 'Performance & device targets',
    group: 'Start here',
    source: 'docs/performance.md',
    description:
      'Measured 10,000-memory Mac runs, unverified ARM goals and native mobile acceptance gates.',
  },
  {
    slug: 'local-first',
    title: 'Local memory & ARM',
    group: 'Start here',
    source: 'docs/local-first.md',
    description:
      'Offline operation, smaller budgets, embedded Rust and device support limits.',
  },
  {
    slug: 'choosing-instantkv',
    title: 'Why instantKV',
    group: 'Start here',
    source: 'docs/choosing-instantkv.md',
    description:
      'Who it helps, what makes it useful and when another memory tool fits better.',
  },
  {
    slug: 'live-demo',
    title: 'Demo architecture',
    group: 'Start here',
    source: 'docs/live-demo.md',
    description:
      'Recorded Mac playback, client caching and live VPS storage measurements.',
  },
  {
    slug: 'quickstart',
    title: 'Quick start',
    group: 'Start here',
    source: 'docs/quickstart.md',
    description:
      'Install instantKV, store your first memory and restore a checkpoint.',
  },
  {
    slug: 'features',
    title: 'Features',
    group: 'Start here',
    source: 'docs/features.md',
    description:
      'What you can use in the current release, with links to each feature.',
  },
  {
    slug: 'demo',
    title: 'Run the demo',
    group: 'Start here',
    source: 'docs/demo.md',
    description:
      'Watch memory survive context clearing and a real server restart.',
  },
  {
    slug: 'cloud-agents',
    title: 'Local agents & swarms',
    group: 'Use the service',
    source: 'docs/cloud-agents.md',
    description:
      'Give workers shared project facts and separate private notes.',
  },
  {
    slug: 'agents',
    title: 'Connect through MCP',
    group: 'Use the service',
    source: 'docs/agents.md',
    description:
      'Four everyday memory tools plus seven KV/checkpoint tools and a save/restore contract.',
  },
  {
    slug: 'cli',
    title: 'CLI reference',
    group: 'Use the service',
    source: 'docs/cli.md',
    description:
      'Commands for records, checkpoints, setup, health and benchmarks.',
  },
  {
    slug: 'http',
    title: 'HTTP reference',
    group: 'Use the service',
    source: 'docs/http.md',
    description:
      'Authenticated routes, conditional writes, TTL, errors and examples.',
  },
  {
    slug: 'agent-memory',
    title: 'Memory & compaction',
    group: 'Use the service',
    source: 'docs/agent-memory.md',
    description: 'What to save before compaction and how to load it afterward.',
  },
  {
    slug: 'configuration',
    title: 'Configuration',
    group: 'Run a node',
    source: 'docs/configuration.md',
    description: 'Set permissions, storage limits, expiry and request limits.',
  },
  {
    slug: 'operations',
    title: 'Operations & backups',
    group: 'Run a node',
    source: 'docs/operations.md',
    description:
      'Health, remote access, offline backup, restore drills and upgrades.',
  },
  {
    slug: 'benchmarks',
    title: 'Benchmark methodology',
    group: 'Run a node',
    source: 'docs/benchmarks.md',
    description:
      'Recorded workloads, hardware, load conditions and reproduction commands.',
  },
  {
    slug: 'architecture',
    title: 'Architecture & schema',
    group: 'Build with us',
    source: 'docs/architecture.md',
    description:
      'Rust, the bounded engine, redb transactions and storage schema.',
  },
  {
    slug: 'contributing',
    title: 'Contributing',
    group: 'Build with us',
    source: 'CONTRIBUTING.md',
    description:
      'Source map, local checks, invariants and the contribution workflow.',
  },
  {
    slug: 'security',
    title: 'Security',
    group: 'Build with us',
    source: 'SECURITY.md',
    description:
      'Report vulnerabilities privately and understand deployment boundaries.',
  },
  {
    slug: 'inspirations',
    title: 'Engineering references',
    group: 'Build with us',
    source: 'docs/inspirations.md',
    description: 'Practices adopted from database, low-level and KDE projects.',
  },
  {
    slug: 'website',
    title: 'Website & deployment',
    group: 'Build with us',
    source: 'docs/website.md',
    description: 'Build, verify and deploy this static Cloudflare site.',
  },
  {
    slug: 'roadmap',
    title: 'Roadmap',
    group: 'Project',
    source: 'docs/roadmap.md',
    description:
      'Source MVP, real local-agent evaluation, native mobile embedding and optional richer retrieval.',
  },
  {
    slug: 'distributed-memory',
    title: 'Distributed memory proposal',
    group: 'Project',
    source: 'docs/distributed-memory.md',
    description:
      'Future historical memory branches, continuous shared updates and peer awareness.',
  },
  {
    slug: 'changelog',
    title: 'Changelog',
    group: 'Project',
    source: 'CHANGELOG.md',
    description: 'Changes by release and work awaiting the next release.',
  },
  {
    slug: 'checkpoints',
    title: 'Verified checkpoints',
    group: 'Project',
    source: 'docs/checkpoints.md',
    description: 'What changed at each stage and how we checked it.',
  },
  {
    slug: 'request-audit',
    title: 'Request audit',
    group: 'Project',
    source: 'docs/request-audit.md',
    description:
      'Requested scope compared with shipped behavior and future proposals.',
  },
] as const;
export const groups = [...new Set(docs.map((doc) => doc.group))];
