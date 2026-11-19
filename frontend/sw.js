
// Service Worker: guarda los archivos
// necesarios para abrir la PWA sin internet.
//
// Las operaciones financieras pendientes
// se almacenan en IndexedDB, no en Cache API.


const VERSION = 'fp-v15';

const ARCHIVOS = [
  './',
  'index.html',
  'manifest.webmanifest',
  'icons/icono.svg',
  'css/estilos.css',

  'js/app.js',
  'js/api.js',
  'js/config.js',
  'js/sesion.js',
  'js/offline.js',
  'js/offline-db.js',
  'js/sync.js',
  'js/util.js',

  'js/vistas/comun.js',
  'js/vistas/login.js',
  'js/vistas/registro.js',
  'js/vistas/inicio.js',
  'js/vistas/crear-cuenta.js',
  'js/vistas/editar-cuenta.js',
  'js/vistas/categorias.js',
  'js/vistas/registrar.js',
  'js/vistas/transferir.js',
  'js/vistas/abonar.js',
  'js/vistas/movimientos.js',
  'js/vistas/deudas.js',
  'js/vistas/metas.js',
  'js/vistas/asistente.js'
];


// INSTALACION
self.addEventListener('install', evento => {
  evento.waitUntil(
    caches.open(VERSION)
      .then(cache => cache.addAll(ARCHIVOS))
      .then(() => self.skipWaiting())
  );
});


// ACTIVACION
self.addEventListener('activate', evento => {
  evento.waitUntil(
    caches.keys()
      .then(claves => Promise.all(
        claves
          .filter(clave => clave !== VERSION)
          .map(clave => caches.delete(clave))
      ))
      .then(() => self.clients.claim())
  );
});


// CACHE DE ARCHIVOS ESTATICOS
self.addEventListener('fetch', evento => {
  const url = new URL(evento.request.url);

  // No interceptar escrituras financieras
  // ni peticiones al backend en otro origen.
  if (
    evento.request.method !== 'GET' ||
    url.origin !== self.location.origin
  ) {
    return;
  }

  evento.respondWith(
    fetch(evento.request)
      .then(respuesta => {
        const copia = respuesta.clone();

        if (respuesta.ok) {
          caches.open(VERSION)
            .then(cache => cache.put(
              evento.request,
              copia
            ))
            .catch(() => {});
        }

        return respuesta;
      })
      .catch(async () => {
        const guardada = await caches.match(
          evento.request
        );

        if (guardada) {
          return guardada;
        }

        if (evento.request.mode === 'navigate') {
          return caches.match('index.html');
        }

        return Response.error();
      })
  );
});
