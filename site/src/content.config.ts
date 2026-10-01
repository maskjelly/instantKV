import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';

const guides = defineCollection({
  loader: glob({
    base: '..',
    pattern: ['docs/*.md', 'CONTRIBUTING.md', 'SECURITY.md', 'CHANGELOG.md'],
    generateId: ({ entry }) =>
      entry
        .replace(/^docs\//, '')
        .replace(/\.md$/, '')
        .toLowerCase(),
  }),
});
export const collections = { guides };
