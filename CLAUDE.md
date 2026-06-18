# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Astro Starlight documentation site. Uses Astro v5 with the Starlight integration for structured documentation.

## Git

Branch off `main` using the naming convention `main.<feature>` (e.g. `main.ci-fixes`).

## Commands

| Command | Action |
|---|---|
| `npm run dev` | Start dev server at `localhost:4321` |
| `npm run build` | Production build to `./dist/` |
| `npm run preview` | Preview production build locally |
| `npm run astro -- --help` | Astro CLI help |

No test framework is configured.

## Architecture

- **Framework:** Astro 5 + Starlight (`@astrojs/starlight`)
- **Config:** `astro.config.mjs` — Starlight plugin config, sidebar structure, site metadata
- **Content:** `src/content/docs/` — Markdown/MDX files, file paths map directly to URL routes
- **Content schema:** `src/content.config.ts` — uses Starlight's `docsLoader()` and `docsSchema()`
- **Static assets:** `public/` for files served as-is, `src/assets/` for processed images
- **TypeScript:** Strict mode via `astro/tsconfigs/strict`

## Sidebar Configuration

The sidebar is defined in `astro.config.mjs`. Sections can use explicit entries or `autogenerate` from a directory:

```js
sidebar: [
  { label: 'Guides', items: [{ label: 'Example Guide', slug: 'guides/example' }] },
  { label: 'Reference', autogenerate: { directory: 'reference' } },
]
```

## Adding Content

Add `.md` or `.mdx` files to `src/content/docs/`. Each file needs frontmatter with at least `title`. MDX files can import and use Starlight components (e.g., `<Card>`, `<CardGrid>`).
