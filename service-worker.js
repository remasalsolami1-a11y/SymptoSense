const CACHE_NAME = 'symptosense-shell-v268';
const APP_SHELL = [
  '/offline', '/static/css/offline.css?v=193', '/static/js/offline.js?v=193',
  '/assets/app-shell-v112.css?v=268',
  '/static/images/body-map-front-v241.png', '/static/images/body-front-v245.webp', '/static/images/body-back-v245.webp',
  '/icons/icon-192.png', '/icons/icon-512.png', '/icons/apple-touch-icon.png', '/favicon.ico', '/brand-icon.svg'
];

// A missing optional asset must never abort Service Worker installation.
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.allSettled(APP_SHELL.map(async url => {
      try {
        const response = await fetch(url, {cache: 'reload'});
        if (response && response.ok) await cache.put(url, response.clone());
      } catch (_) {}
    }));
    await self.skipWaiting();
  })());
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('symptosense-') && k !== CACHE_NAME).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request=event.request; if(request.method!=='GET')return;
  const earlyUrl=new URL(request.url);
  // Authenticated API responses must always go straight to the network.
  // Never let a Service Worker participate in medication/account API reads.
  if(earlyUrl.origin===self.location.origin&&earlyUrl.pathname.startsWith('/api/'))return;
  if(earlyUrl.origin===self.location.origin&&earlyUrl.pathname.endsWith('.xlsx'))return;
  if(request.mode==='navigate'){event.respondWith(fetch(request).catch(()=>caches.match('/offline')));return;}
  const url=new URL(request.url);
  if(url.origin===self.location.origin && url.pathname==='/manifest.webmanifest'){
    event.respondWith(fetch(request).catch(()=>caches.match(request)));
    return;
  }
  if(url.origin===self.location.origin&&url.pathname.startsWith('/assets/')){
    event.respondWith(caches.match(request).then(cached=>cached||fetch(request).then(response=>{
      if(response&&response.ok){const copy=response.clone();caches.open(CACHE_NAME).then(cache=>cache.put(request,copy));}
      return response;
    })));
    return;
  }
  // Versioned/immutable assets are cache-first. Other static assets use
  // stale-while-revalidate so navigation never waits on CSS/JS network latency.
  const isStatic=url.origin===self.location.origin&&url.pathname.startsWith('/static/');
  if(isStatic){
    const immutable=url.searchParams.has('v')||url.pathname.includes('app-shell-v112.');
    if(immutable){
      event.respondWith(caches.match(request).then(cached=>cached||fetch(request).then(response=>{
        if(response&&response.ok){const copy=response.clone();caches.open(CACHE_NAME).then(cache=>cache.put(request,copy));}
        return response;
      })));
    }else{
      event.respondWith(caches.match(request).then(cached=>{
        const refresh=fetch(request).then(response=>{
          if(response&&response.ok){const copy=response.clone();caches.open(CACHE_NAME).then(cache=>cache.put(request,copy));}
          return response;
        }).catch(()=>cached);
        return cached||refresh;
      }));
    }
    return;
  }
  const immutable=url.origin===self.location.origin&&(url.pathname.startsWith('/icons/')||url.pathname==='/favicon.ico'||url.pathname==='/brand-icon.svg');
  if(immutable) event.respondWith(caches.match(request).then(cached=>cached||fetch(request).then(response=>{if(response&&response.ok){const copy=response.clone();caches.open(CACHE_NAME).then(cache=>cache.put(request,copy));}return response;})));
});
