// Very small service worker for offline shell caching

// Bump the cache name whenever we change core assets like app.js
// so that users always get the latest frontend code.
const CACHE_NAME = 'shih-tzu-app-v16';
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
  // Network first for API, cache first for static assets
  const url = new URL(request.url);
  if (url.pathname.startsWith('/api/')) {
    return; // let the network handle API calls
  }
  event.respondWith(
    caches.match(request).then((cached) =>
      cached || fetch(request).catch(() => caches.match('/index.html'))
    )
  );
});
