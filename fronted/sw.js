// Service Worker: guarda el "cascarón" de la app para que abra sin internet.
// Las llamadas al backend no se guardan aquí; los movimientos sin conexión
// van a IndexedDB (js/offline.js).

const VERSION = 'fp-v6';
const ARCHIVOS = [
  './',
  'index.html',
  'manifest.webmanifest',
  'icons/icono.svg',
  'css/estilos.css',
  'js/app.js', 'js/api.js', 'js/config.js', 'js/sesion.js', 'js/offline.js', 'js/offline-db.js', 'js/sync.js', 'js/util.js',
  'js/vistas/comun.js', 'js/vistas/login.js', 'js/vistas/registro.js', 'js/vistas/inicio.js', 'js/vistas/crear-cuenta.js',
  'js/vistas/registrar.js', 'js/vistas/transferir.js', 'js/vistas/abonar.js', 'js/vistas/movimientos.js', 'js/vistas/deudas.js',
  'js/vistas/metas.js', 'js/vistas/asistente.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(ARCHIVOS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((claves) => Promise.all(claves.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Mismo origen: primero la red (para ver cambios al desarrollar), si falla, la caché.
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== self.location.origin) return;
  e.respondWith(
    fetch(e.request)
      .then((r) => {
        const copia = r.clone();
        caches.open(VERSION).then((c) => c.put(e.request, copia));
        return r;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match('index.html')))
  );
});
