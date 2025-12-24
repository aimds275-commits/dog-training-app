// Very small service worker for offline shell caching

// Bump the cache name whenever we change core assets like app.js
// so that users always get the latest frontend code.
const CACHE_NAME = 'shih-tzu-app-v17';
const ASSETS = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/manifest.webmanifest'
];

self.addEventListener('install', (event) => {
  // Skip waiting to activate immediately
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

self.addEventListener('activate', (event) => {
  // Take control of all clients immediately
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  // Let the network handle API calls
  if (url.pathname.startsWith('/api/')) return;

  // For navigation requests (user entering the app / SPA routing),
  // use network-first with an index.html fallback. For other static
  // assets (JS/CSS/images), use cache-first and do NOT return
  // index.html as a fallback, which would cause JS parsing errors.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/index.html'))
    );
    return;
  }

  // Cache-first for static assets
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request))
  );
});
