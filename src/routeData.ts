import { defineRouteMiddleware } from '@astrojs/starlight/route-data';

export const onRequest = defineRouteMiddleware((context) => {
  // URL of the generated Open Graph image for the current page.
  const ogImageUrl = new URL(
    `/og/${context.locals.starlightRoute.id || 'index'}.png`,
    context.site,
  );

  const { head } = context.locals.starlightRoute;

  head.push({
    tag: 'meta',
    attrs: { property: 'og:image', content: ogImageUrl.href },
  });
  head.push({
    tag: 'meta',
    attrs: { name: 'twitter:image', content: ogImageUrl.href },
  });

  // Advertise the generated llms.txt files so HTML-parsing agents can discover them.
  const llmsUrl = new URL('/llms.txt', context.site);
  const llmsFullUrl = new URL('/llms-full.txt', context.site);

  head.push({
    tag: 'link',
    attrs: { rel: 'alternate', type: 'text/plain', title: 'llms.txt', href: llmsUrl.href },
  });
  head.push({
    tag: 'link',
    attrs: { rel: 'alternate', type: 'text/plain', title: 'llms-full.txt', href: llmsFullUrl.href },
  });
});
