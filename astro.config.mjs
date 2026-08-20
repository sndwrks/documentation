// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightThemeFlexoki from 'starlight-theme-flexoki'
import astroExpressiveCode from 'astro-expressive-code'
import starlightImageZoom from 'starlight-image-zoom'
import mermaid from 'astro-mermaid'
import { unified } from '@astrojs/markdown-remark';

import sitemap from '@astrojs/sitemap';

import rehypeSections from './src/plugins/rehype-sections.mjs';

// https://astro.build/config
export default defineConfig({
  site: 'https://docs.sndwrks.com',
  build: { format: 'directory' },
  markdown: {
    processor: unified({ rehypePlugins: [rehypeSections] }),
  },
    integrations: [mermaid({
        autoTheme: true,
        mermaidConfig: {
            // Mermaid namespaces themeCSS under the same `#<svg-id>` prefix as its
            // own rules but PREPENDS it, so ties go to mermaid — hence !important.
            // Everything here reads the house tokens, so light/dark comes free.
            themeCSS: `
              .node rect, .node polygon, .node circle, .node ellipse, .node path,
              .node .label-container {
                fill: var(--color-surface-sunken) !important;
                stroke: var(--color-rule-strong) !important;
                stroke-width: 1px !important;
                rx: 0 !important;
                ry: 0 !important;
              }
              .nodeLabel, .nodeLabel p, .label, .label span, .label foreignObject div {
                color: var(--color-text) !important;
                fill: var(--color-text) !important;
                font-family: inherit !important;
              }
              .edgePath .path, .flowchart-link,
              .edge-thickness-normal, .edge-thickness-thick {
                stroke: var(--color-rule-strong) !important;
              }
              marker path, .arrowheadPath, .marker {
                fill: var(--color-rule-strong) !important;
                stroke: var(--color-rule-strong) !important;
              }
              .edgeLabel rect, .edgeLabel .labelBkg, .labelBkg {
                fill: var(--color-bg) !important;
                background-color: var(--color-bg) !important;
                opacity: 1 !important;
              }
              .edgeLabel, .edgeLabel p, .edgeLabel span {
                color: var(--color-muted) !important;
                fill: var(--color-muted) !important;
                background-color: var(--color-bg) !important;
                font-family: var(--sl-font-system-mono) !important;
              }
              .cluster rect {
                fill: transparent !important;
                stroke: var(--color-rule) !important;
                stroke-width: 1px !important;
                rx: 0 !important;
                ry: 0 !important;
              }
              .cluster-label, .cluster-label p, .cluster span {
                color: var(--color-accent-text) !important;
                fill: var(--color-accent-text) !important;
                font-family: var(--sl-font-system-mono) !important;
              }
            `,
        },
    }), astroExpressiveCode({
        themes: ['catppuccin-mocha', 'catppuccin-latte'],
        themeCssSelector: (theme) => `[data-theme='${theme.type}']`,
        useDarkModeMediaQuery: false,
        styleOverrides: {
            borderRadius: '0',
            borderWidth: '1px',
            borderColor: 'var(--color-rule)',
            codeBackground: 'var(--color-surface-sunken)',
            frames: {
                frameBoxShadowCssValue: 'none',
                terminalTitlebarBorderBottomColor: 'var(--color-rule)',
                terminalTitlebarBackground: 'var(--color-surface-raised)',
                editorTabBarBackground: 'var(--color-surface-raised)',
                editorActiveTabIndicatorTopColor: 'var(--color-accent)',
            },
        },
    }), starlight({
        title: 'documentation',
        routeMiddleware: './src/routeData.ts',
        social: [{ icon: 'discord', label: 'Discord', href: 'https://discord.gg/Fe3mPqwxyn' },{ icon: 'github', label: 'GitHub', href: 'https://github.com/sndwrks/documentation' }],
  logo: {
    src: './src/assets/sndwrks-logo.svg'
  },
  favicon: '/favicon.svg',
        sidebar: [
    {
      label: 'Products',
      items: [
        'products/sndwrks-local/home',
        {
          label: 'Server Hardware',
          items: [{ autogenerate: { directory: 'products/sndwrks-local/server-hardware' } }]
        },
        {
          label: 'Software',
          items: [{ autogenerate: { directory: 'products/sndwrks-local/software' } }]
        }
      ]
    },
            {
                label: 'Guides',
      items: [{ autogenerate: { directory: 'guides' } }],
            },
            {
                label: 'Reference',
                items: [{ autogenerate: { directory: 'reference' } }],
            },
        ],
  plugins: [
    starlightThemeFlexoki({
      accentColor: 'purple',
    }),
    starlightImageZoom(),
  ],
  components: {
    Footer: './src/components/Footer.astro',
    Pagination: './src/components/Pagination.astro',
    Hero: './src/components/Hero.astro',
  },
  customCss: [
    './src/styles/custom.css'
  ],
		}), sitemap()],
});