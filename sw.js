/* MasterForge AI v1.0.0-beta: app shell only, never cache a user's audio. */
const CACHE_NAME = 'masterforge-shell-v1.0.0-beta';
const APP_SHELL = [
  './','./index.html',
  './app.js?v=1.0.0-beta','./web-mastering.js?v=1.0.0-beta','./theme.js?v=1.0.0-beta','./styles.css?v=1.0.0-beta',
  './manifest.webmanifest','./assets/icon-192.png',
  './assets/icon-512.png','./assets/apple-touch-icon.png'
];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(APP_SHELL)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(Promise.all([
    caches.keys().then(names=>Promise.all(names.filter(n=>n.startsWith('masterforge-shell-')&&n!==CACHE_NAME).map(n=>caches.delete(n)))),
    self.clients.claim()
  ]));
});
self.addEventListener('fetch',event=>{
  const request=event.request;
  if(request.method!=='GET')return;
  const url=new URL(request.url);
  if(url.href==='https://cdn.jsdelivr.net/npm/lamejs@1.2.1/lame.min.js'){
    event.respondWith(caches.open(CACHE_NAME).then(async cache=>{
      const stored=await cache.match(request);
      if(stored)return stored;
      const response=await fetch(request);
      if(response.ok||response.type==='opaque')await cache.put(request,response.clone());
      return response;
    }));
    return;
  }
  if(url.origin!==self.location.origin)return;
  if(!url.pathname.startsWith(new URL(self.registration.scope).pathname))return;
  // Network-first for executable app code and HTML, cache fallback for offline operation.
  // Versioned script URLs prevent an old service worker from pairing older engine JS
  // with a newly deployed Signature button.
  if(request.mode==='navigate'||['script','style'].includes(request.destination)){
    event.respondWith(caches.open(CACHE_NAME).then(async cache=>{
      try {
        const response=await fetch(request);
        if(response.ok) await cache.put(request,response.clone());
        return response;
      } catch(error) {
        const cached=await cache.match(request,{ignoreSearch:true});
        if(cached)return cached;
        if(request.mode==='navigate'){
          const shell=await cache.match('./index.html');
          if(shell)return shell;
        }
        throw error;
      }
    }));
    return;
  }
  event.respondWith(caches.match(request,{ignoreSearch:true}).then(hit=>hit||fetch(request)));
});
