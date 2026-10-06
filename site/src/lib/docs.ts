export const repository = 'https://github.com/maskjelly/instantKV';
export const docs = [
  {
    slug: 'quickstart',
    title: 'Quick start',
    group: 'Start here',
    source: 'docs/quickstart.md',
    description:
      'Install instantKV, store your first memory and restore a checkpoint.',
  },
  {
    slug: 'agents',
    title: 'Connect through MCP',
    group: 'Start here',
    source: 'docs/agents.md',
    description:
      'Five memory tools, seven KV/checkpoint tools and checkpoint instructions.',
  },
  {
    slug: 'opencode-memory-demo',
    title: 'OpenCode memory setup',
    group: 'Start here',
    source: 'docs/opencode-memory-demo.md',
    description:
      'Install local MCP memory for OpenCode and run an explicit save, restart and recall demonstration.',
  },
  {
    slug: 'memory-mvp',
    title: 'Memory API & local models',
    group: 'Start here',
    source: 'docs/memory-mvp.md',
    description:
      'Remember, recall, search, browse and forget. Find memories by topic, tag, time or keywords. Try the local-model example.',
  },
  {
    slug: 'agent-memory',
    title: 'Memory & compaction',
    group: 'Use the service',
    source: 'docs/agent-memory.md',
    description: 'What to save before compaction and how to load it afterward.',
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
    slug: 'cli',
    title: 'CLI reference',
    group: 'Use the service',
    source: 'docs/cli.md',
    description:
      'Commands for structured memories, checkpoints, setup and health.',
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
    slug: 'local-first',
    title: 'Local memory & ARM',
    group: 'Run a node',
    source: 'docs/local-first.md',
    description:
      'Offline operation, smaller budgets, embedded Rust and device support limits.',
  },
  {
    slug: 'performance',
    title: 'Performance & device targets',
    group: 'Evidence',
    source: 'docs/performance.md',
    description:
      'Full retrieval results, Mac measurements and planned phone tests.',
  },
  {
    slug: 'full-retrieval',
    title: 'Full retrieval report',
    group: 'Evidence',
    source: 'docs/benchmarks/2026-10-04-full-retrieval/README.md',
    description:
      'All 500 LongMemEval-S questions and all ten LoCoMo histories.',
  },
  {
    slug: 'benchmarks',
    title: 'Benchmark methodology',
    group: 'Evidence',
    source: 'docs/benchmarks.md',
    description:
      'Recorded workloads, hardware, load conditions and reproduction commands.',
  },
  {
    slug: 'evaluation-policy',
    title: 'Evaluation policy',
    group: 'Evidence',
    source: 'docs/evaluation-policy.md',
    description:
      'Frozen tests, reproducible results and honest comparison limits.',
  },
  {
    slug: 'memory-benchmark-notes',
    title: 'Memory benchmark notes',
    group: 'Evidence',
    source: 'docs/memory-benchmark-notes.md',
    description:
      'Full memory suites, retrieval wins, remaining gaps and raw evidence.',
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
    slug: 'repository',
    title: 'Repository maintenance',
    group: 'Build with us',
    source: 'docs/repository.md',
    description:
      'File ownership, canonical guides, review rules and verification.',
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
    slug: 'website',
    title: 'Website & deployment',
    group: 'Build with us',
    source: 'docs/website.md',
    description: 'Build, verify and deploy this static Cloudflare site.',
  },
  {
    slug: 'discovery',
    title: 'Search & agent discovery',
    group: 'Build with us',
    source: 'docs/discovery.md',
    description:
      'Canonical pages, Markdown exports, crawl checks and evidence-based discoverability.',
  },
  {
    slug: 'install-metrics',
    title: 'Private installation reporting',
    group: 'Build with us',
    source: 'docs/install-metrics.md',
    description:
      'Keep download evidence in a private local ledger. Counting and privacy limits.',
  },
  {
    slug: 'inspirations',
    title: 'Engineering references',
    group: 'Build with us',
    source: 'docs/inspirations.md',
    description: 'Practices adopted from database, low-level and KDE projects.',
  },
  {
    slug: 'project-plan',
    title: 'Cleanup & release plan',
    group: 'Project',
    source: 'docs/project-plan.md',
    description: 'Ordered work, release gates and validation requirements.',
  },
  {
    slug: 'roadmap',
    title: 'Roadmap',
    group: 'Project',
    source: 'docs/roadmap.md',
    description:
      'Source MVP status, local-model evaluation, phone integration and optional retrieval plans.',
  },
  {
    slug: 'choosing-instantkv',
    title: 'Local AI memory: when instantKV fits',
    group: 'Project',
    source: 'docs/choosing-instantkv.md',
    description:
      'Who it helps, what makes it useful and when another memory tool fits better.',
  },
  {
    slug: 'features',
    title: 'Features',
    group: 'Project',
    source: 'docs/features.md',
    description: 'Available features, the source MVP and planned work.',
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
    title: 'Verification history',
    group: 'History',
    source: 'docs/history/checkpoints.md',
    description: 'What changed at each stage and how we checked it.',
  },
  {
    slug: 'distributed-memory',
    title: 'Distributed memory proposal',
    group: 'Proposals',
    source: 'docs/proposals/distributed-memory.md',
    description: 'Proposed snapshot branches, shared updates and peer status.',
  },
] as const;
export const groups = [...new Set(docs.map((doc) => doc.group))];
