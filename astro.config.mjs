// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightThemeFlexoki from 'starlight-theme-flexoki'
import astroExpressiveCode from 'astro-expressive-code'

// https://astro.build/config
export default defineConfig({
	integrations: [
    astroExpressiveCode({
        themes: ['monokai']
    }),
		starlight({
			title: 'documentation',
			social: [{ icon: 'discord', label: 'Discord', href: 'https://discord.gg/tjPd6Q9A' },{ icon: 'github', label: 'GitHub', href: 'https://github.com/sndwrks' }],
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
              autogenerate: { directory: 'products/sndwrks-local/server-hardware'}
            }
          ]
        },
				{
					label: 'Guides',
          autogenerate: { directory: 'guides' },
				},
				{
					label: 'Reference',
					autogenerate: { directory: 'reference' },
				},
			],
      plugins: [
        starlightThemeFlexoki({
          accentColor: 'green',
        })
      ],
      customCss: [
        './src/styles/custom.css'
      ],
		}),
	],
});

