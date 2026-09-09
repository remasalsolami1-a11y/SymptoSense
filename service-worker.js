const CACHE_NAME = 'symptosense-shell-v8-competition-ready';
const APP_SHELL = [
  '/offline', '/icons/icon-192.png',
  '/icons/icon-512.png', '/icons/apple-touch-icon.png', '/favicon.ico', '/brand-icon.svg'
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
  if(request.mode==='navigate'){event.respondWith(fetch(request).catch(()=>caches.match('/offline')));return;}
  const url=new URL(request.url);
  if(url.origin===self.location.origin && url.pathname==='/manifest.webmanifest'){
    event.respondWith(fetch(request).catch(()=>caches.match(request)));
    return;
  }
  const safe=url.origin===self.location.origin&&(url.pathname.startsWith('/icons/')||url.pathname.startsWith('/static/')||url.pathname==='/favicon.ico'||url.pathname==='/brand-icon.svg');
  if(safe) event.respondWith(caches.match(request).then(cached=>cached||fetch(request).then(response=>{if(response&&response.ok){const copy=response.clone();caches.open(CACHE_NAME).then(cache=>cache.put(request,copy));}return response;})));
});

self.addEventListener('push', event => {
  let data={};
  try{data=event.data?event.data.json():{};}catch(e){data={title:'SymptoSense',body:event.data?event.data.text():''};}
  const options={
    body:data.body||'لديك تذكير صحي', icon:data.icon||'/icons/icon-192.png', badge:data.badge||'/icons/icon-192.png',
    tag:data.tag||'symptosense-medication', renotify:true, silent:!!data.silent,
    data:{url:data.url||'/meds',token:data.token||''}
  };
  if(data.token){options.actions=[{action:'taken',title:data.taken_label||'Taken'},{action:'snooze',title:data.snooze_label||'Snooze'}];}
  event.waitUntil(self.registration.showNotification(data.title||'💊 SymptoSense',options));
});
async function postAction(token, action){
  if(!token||!action)return;
  try{await fetch('/api/push/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token,action})});}catch(e){}
}
async function focusOrOpen(url){
  const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
  for(const client of windows){if('focus' in client){try{await client.navigate(url);}catch(e){} return client.focus();}}
  if(self.clients.openWindow)return self.clients.openWindow(url);
}
self.addEventListener('notificationclick', event => {
  event.notification.close(); const data=event.notification.data||{}; const url=data.url||'/meds';
  event.waitUntil((async()=>{
    if(event.action==='taken'||event.action==='snooze'){await postAction(data.token,event.action);return;}
    return focusOrOpen(url);
  })());
});
