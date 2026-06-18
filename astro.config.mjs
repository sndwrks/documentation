// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightThemeFlexoki from 'starlight-theme-flexoki'
import astroExpressiveCode from 'astro-expressive-code'
import starlightImageZoom from 'starlight-image-zoom'

// https://astro.build/config
export default defineConfig({
	integrations: [
    astroExpressiveCode({
        themes: ['monokai']
    }),
		starlight({
			title: 'documentation',
			social: [{ icon: 'discord', label: 'Discord', href: 'https://discord.gg/tjPd6Q9A' },{ icon: 'github', label: 'GitHub', href: 'https://github.com/sndwrks/documentation' }],
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
		}),
	],
});

