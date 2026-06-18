import { getCollection } from 'astro:content';
import { OGImageRoute } from 'astro-og-canvas';

// Get all entries from the `docs` content collection.
const entries = await getCollection('docs');

// Map the entry array to an object keyed by page ID with its frontmatter data.
const pages = Object.fromEntries(entries.map(({ data, id }) => [id, { data }]));

export const { getStaticPaths, GET } = await OGImageRoute({
  // Pass down the documentation pages.
  pages,
  // Matches the `[...slug].ts` route parameter.
  param: 'slug',
  // Customize the generated image for each page.
  getImageOptions: (_id, page: (typeof pages)[string]) => ({
    title: page.data.title,
    description: page.data.description,
    // Branded background (lime green + "sndwrks" wordmark top-left); page text
    // is overlaid below the wordmark.
    bgImage: { path: './public/sndwrks-og-no-cta.png', fit: 'cover' },
    // Uniform padding pushes the title below the top-left wordmark.
    padding: 150,
    font: {
      // Dark text for contrast against the light green background.
      title: { color: [39, 39, 42], size: 64, weight: 'Bold' },
      description: { color: [63, 63, 70], size: 30 },
    },
  }),
});
