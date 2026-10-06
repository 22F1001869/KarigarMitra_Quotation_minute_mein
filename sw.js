// KarigarMitra offline cache. Change VERSION after every update you upload.
const VERSION='karigarmitra-v6';
const FILES=['./','./index.html','./manifest.json','./icons/icon-96.png','./icons/icon-180.png','./icons/icon-192.png','./icons/icon-512.png','./icons/maskable-192.png','./icons/maskable-512.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(VERSION).then(c=>c.addAll(FILES)));self.skipWaiting()});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==VERSION).map(x=>caches.delete(x)))));self.clients.claim()});
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);
  if(e.request.method!=='GET'||u.pathname.includes('/api/')) return;   // never cache the stats API
  if(e.request.mode==='navigate'){e.respondWith(fetch(e.request).then(r=>{const cp=r.clone();caches.open(VERSION).then(c=>c.put('./index.html',cp));return r}).catch(()=>caches.match('./index.html')));return}
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)))});
