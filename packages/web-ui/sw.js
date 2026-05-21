/* ICECODE Service Worker — offline support for static assets */
const CACHE = 'icecode-v3';
const OFFLINE_URL = '/';

// Cache static assets on install
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(['/']))
      .then(() => self.skipWaiting())
  );
});

// Remove old caches on activate
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Network-first for API calls, cache-first for static
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // Always fetch API calls from network
  if (url.pathname.startsWith('/api/') || url.pathname === '/health') {
    e.respondWith(fetch(e.request).catch(() =>
      new Response(JSON.stringify({ error: 'offline' }), {
        headers: { 'Content-Type': 'application/json' }
      })
    ));
    return;
  }

  // Cache-first for the main HTML page
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request)
      .then(resp => {
        if (resp.ok) {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      })
      .catch(() => caches.match(OFFLINE_URL))
    )
  );
});
