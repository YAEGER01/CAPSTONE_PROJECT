const CACHE_NAME = 'caufa-static-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/img/isu_caufa_official_192.png',
  '/static/img/isu_caufa_official_512.png',
  '/static/img/isugym.jpg',
  '/static/img/halfdesignISU.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

// Simple cache-first strategy for same-origin static assets, network-first for others
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle GET
  if (request.method !== 'GET') return;

  // For same-origin static resources (under /static/), use cache-first
  if (url.origin === location.origin && url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const fetched = fetch(request).then((resp) => {
          if (resp && resp.ok) {
            // clone + cache but guard against failures when body already used
            const respClone = resp.clone();
            caches.open(CACHE_NAME).then(cache => {
              try {
                cache.put(request, respClone);
              } catch (e) {
                // Defensive: some responses may not be cloneable or may error
                console.warn('ServiceWorker: cache.put failed for', request.url, e);
              }
            }).catch(e => console.warn('ServiceWorker: open cache failed', e));
          }
          return resp;
        }).catch(() => null);
        return cached || fetched;
      })
    );
    return;
  }

  // Network-first for navigation and API calls
  event.respondWith(
    fetch(request).then((resp) => {
      return resp;
    }).catch(() => caches.match(request))
  );
});
