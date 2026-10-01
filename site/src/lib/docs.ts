export const repository = 'https://github.com/maskjelly/instantKV';
export const docs = [
  {
    slug: 'live-demo',
    title: 'Live demo architecture',
    group: 'Start here',
    source: 'docs/live-demo.md',
    description:
      'Real Rust storage, independent readers and reproducible latency measurements.',
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
    description: 'Everything the current single-node service implements.',
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
    title: 'Cloud agents & swarms',
    group: 'Use the service',
    source: 'docs/cloud-agents.md',
    description:
      'Shared knowledge base, private agent namespaces and remote access.',
  },
  {
    slug: 'agents',
    title: 'Connect through MCP',
    group: 'Use the service',
    source: 'docs/agents.md',
    description:
      'Seven typed memory tools and a save/restore contract for agents.',
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
    description:
      'Capsules, stable locators, bounded restores and revision-aware references.',
  },
  {
    slug: 'configuration',
    title: 'Configuration',
    group: 'Run a node',
    source: 'docs/configuration.md',
    description:
      'Strict policies for namespaces, grants, quotas, expiry and admission.',
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
    description: 'Shipped capabilities and the next engineering milestones.',
  },
  {
    slug: 'distributed-memory',
    title: 'Distributed memory proposal',
    group: 'Project',
    source: 'docs/distributed-memory.md',
    description:
      'Future baseline replicas, private overlays and knowledge consolidation.',
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
    description: 'Build stages with concrete validation evidence.',
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
