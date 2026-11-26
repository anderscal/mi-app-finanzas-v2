// Service Worker: solo recursos estaticos de la PWA.

const VERSION = 'fp-v31';

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
  'js/saldo-consulta.js',
  'js/rag-api.js',

  'js/vistas/comun.js',
  'js/vistas/login.js',
  'js/vistas/password.js',
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


const URLS = ARCHIVOS.map(
  ruta => new URL(
    ruta,
    self.registration.scope
  ).href
);

const PERMITIDOS = new Set(URLS);


self.addEventListener('install', evento => {

  evento.waitUntil((async () => {

    const cache = await caches.open(VERSION);

    await cache.addAll(
      URLS.map(
        url => new Request(
          url,
          { cache: 'reload' }
        )
      )
    );

    await self.skipWaiting();

  })());

});


self.addEventListener('activate', evento => {

  evento.waitUntil((async () => {

    const claves = await caches.keys();

    await Promise.all(

      claves.filter(
        clave =>
          clave.startsWith('fp-v') &&
          clave !== VERSION
      ).map(
        clave => caches.delete(clave)
      )

    );

    await self.clients.claim();

  })());

});


self.addEventListener('fetch', evento => {

  const solicitud = evento.request;

  // Nunca interceptar operaciones financieras,
  // solicitudes autenticadas o recursos desconocidos.

  if (
    solicitud.method !== 'GET' ||

    solicitud.headers.has('Authorization') ||

    solicitud.cache === 'no-store' ||

    !PERMITIDOS.has(solicitud.url)
  ) {
    return;
  }

  evento.respondWith((async () => {

    const cache = await caches.open(VERSION);

    const guardado = await cache.match(
      solicitud.url
    );

    if (guardado) {
      return guardado;
    }

    return fetch(solicitud);

  })());

});