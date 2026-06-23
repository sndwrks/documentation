// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightThemeFlexoki from 'starlight-theme-flexoki'
import astroExpressiveCode from 'astro-expressive-code'
import starlightImageZoom from 'starlight-image-zoom'

import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  site: 'https://docs.sndwrks.com',
  build: { format: 'directory' },
    integrations: [astroExpressiveCode({
        themes: ['monokai']
    }), starlight({
        title: 'documentation',
        routeMiddleware: './src/routeData.ts',
        social: [{ icon: 'discord', label: 'Discord', href: 'https://discord.gg/7ZcP5v5kBA' },{ icon: 'github', label: 'GitHub', href: 'https://github.com/sndwrks/documentation' }],
  logo: {
    src: './src/assets/sndwrks-logo.svg'
  },
  favicon: 'favicon.ico',
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
      accentColor: 'green',
    }),
    starlightImageZoom(),
  ],
  customCss: [
    './src/styles/custom.css'
  ],
		}), sitemap()],
});