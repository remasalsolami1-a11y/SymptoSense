const CACHE_NAME = 'symptosense-shell-v8-assets';
const APP_SHELL = [
  '/offline', '/manifest.webmanifest', '/icons/icon-192.png',
  '/icons/icon-512.png', '/icons/apple-touch-icon.png', '/favicon.ico'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('symptosense-') && k !== CACHE_NAME).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

// Only ever cache a response that actually succeeded. A failed fetch (404/403/
// 500/502/opaque-error) is returned to the page as-is and is never written to
// the Cache Storage, so a bad deploy can never leave a permanent stale failure
// behind for later visitors.
function putIfOk(request, response) {
  if (response && response.ok) {
    const copy = response.clone();
    caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
  }
  return response;
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match('/offline')));
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const isImage = request.destination === 'image' || url.pathname.startsWith('/icons/') || url.pathname.startsWith('/static/images/');
  const isShell = url.pathname === '/manifest.webmanifest' || url.pathname === '/favicon.ico';
  if (!isImage && !isShell) return;

  if (isImage) {
    // Network First for images: always ask the live server first so a fresh
    // deployment is visible immediately. Only fall back to a previously-good
    // cached copy if the network request itself fails (offline/timeout).
    event.respondWith(
      fetch(request)
        .then(response => putIfOk(request, response))
        .catch(() => caches.match(request))
    );
    return;
  }

  // Cache First for the small, rarely-changing shell files, but never store
  // a failed response, and always fall through to the network if not cached.
  event.respondWith(
    caches.match(request).then(cached => cached || fetch(request).then(response => putIfOk(request, response)))
  );
});

self.addEventListener('push', event => {
  let data={};
  try{data=event.data?event.data.json():{};}catch(e){data={title:'SymptoSense',body:event.data?event.data.text():''};}
  const options={
    body:data.body||'لديك تذكير صحي', icon:data.icon||'/icons/icon-192.png', badge:data.badge||'/icons/icon-192.png',
    tag:data.tag||'symptosense-medication', renotify:true, silent:!!data.silent,
    data:{url:data.url||'/meds',token:data.token||''}
  };
  // Action buttons are best-effort; some browsers/OS versions ignore them.
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
