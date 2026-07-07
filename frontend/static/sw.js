const CACHE_NAME = "rural-attendance-pwa-v2";
const ASSETS = [
  "/",
  "/health-worker",
  "/supervisor",
  "/static/styles.css",
  "/static/app.js",
  "/static/health-worker.js",
  "/static/supervisor.js",
  "/static/manifest.webmanifest",
  "/static/icon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)));
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(event.request).catch(() => caches.match("/"));
    })
  );
});
