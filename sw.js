// Bachateca: funciona sin conexión. Sube la versión al cambiar archivos para que el iPhone descargue la nueva.
const VERSION = "bachateca-v66";
const ASSETS = ["./", "./index.html", "./manifest.webmanifest", "./icon-180.png", "./icon-192.png", "./icon-512.png", "./icon-maskable-512.png",
  ...[1,2,3,4,5,6,7,8].map(n => `./sonidos/conteo/${n}.m4a`)];
self.addEventListener("install", e => {
  // cache:"reload": baja los archivos de la red, no de la caché del navegador (podría dar los de la versión anterior).
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(ASSETS.map(u => new Request(u, { cache: "reload" })))).then(() => self.skipWaiting()));
});
// Con mala cobertura (p. ej. en un social), la red puede tardar mucho sin fallar: pasados 3 s se abre la copia guardada,
// y la respuesta de la red, si llega, se guarda igual para la próxima vez.
const RED_MAX = 3000;
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
    const guardada = () => app ? caches.match("./index.html") : caches.match(req, { ignoreSearch: true }).then(hit => hit || caches.match("./index.html"));
    const red = fetch(req);
    // El service worker sigue vivo hasta guardar la respuesta, aunque ya se haya abierto la copia guardada.
    e.waitUntil(red.then(res => { if (res.ok) { const cp = res.clone(); return caches.open(VERSION).then(c => c.put(app ? "./index.html" : req, cp)); } }).catch(() => {}));
    e.respondWith(new Promise(resolve => {
      let hecho = false;
      const da = r => { if (!hecho && r) { hecho = true; resolve(r); } };
      // Si la red tarda más de 3 s y hay copia guardada, se abre esa; si no la hay, se sigue esperando a la red.
      const t = setTimeout(() => guardada().then(da), RED_MAX);
      red.then(r => { clearTimeout(t); da(r); }, () => { clearTimeout(t); guardada().then(hit => hit ? da(hit) : da(Response.error())); });
    }));
    return;
  }
  e.respondWith(caches.match(req, { ignoreSearch: true }).then(hit => hit || fetch(req).then(res => {
    if (res.ok) { const cp = res.clone(); caches.open(VERSION).then(c => c.put(req, cp)); }
    return res;
  })));
});
