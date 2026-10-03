import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { docs } from './lib/docs';

const guides = defineCollection({
  loader: glob({
    base: '..',
    pattern: [
      'docs/*.md',
      'docs/benchmarks/2026-10-04-full-retrieval/README.md',
      'CONTRIBUTING.md',
      'SECURITY.md',
      'CHANGELOG.md',
    ],
    generateId: ({ entry }) =>
      docs.find((doc) => doc.source === entry)?.slug ??
      entry
        .replace(/^docs\//, '')
        .replace(/\.md$/, '')
        .toLowerCase(),
  }),
});
export const collections = { guides };
