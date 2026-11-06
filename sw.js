// Bachateca: funciona sin conexión. Sube la versión al cambiar archivos para que el iPhone descargue la nueva.
const VERSION = "bachateca-v48";
const ASSETS = ["./", "./index.html", "./manifest.webmanifest", "./icon-180.png", "./icon-192.png", "./icon-512.png", "./icon-maskable-512.png",
  ...[1,2,3,4,5,6,7,8].map(n => `./sonidos/conteo/${n}.m4a`)];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  if (req.mode === "navigate") {
    // La página: primero la red (para recibir actualizaciones), si no hay conexión, la copia guardada.
    // Solo la app se guarda como index.html; otras páginas (p. ej. conteo.html) se guardan con su nombre.
    const app = /\/(index\.html)?$/.test(new URL(req.url).pathname);
    e.respondWith(fetch(req).then(res => { if (res.ok) { const cp = res.clone(); caches.open(VERSION).then(c => c.put(app ? "./index.html" : req, cp)); } return res; })
      .catch(() => app ? caches.match("./index.html") : caches.match(req, { ignoreSearch: true }).then(hit => hit || caches.match("./index.html"))));
    return;
  }
  e.respondWith(caches.match(req, { ignoreSearch: true }).then(hit => hit || fetch(req).then(res => {
    if (res.ok) { const cp = res.clone(); caches.open(VERSION).then(c => c.put(req, cp)); }
    return res;
  })));
});
