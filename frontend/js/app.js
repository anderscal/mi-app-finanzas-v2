// Punto de entrada: rutas por hash, barra de navegación y sincronización offline.


import { haySesion } from './sesion.js';
import { sincronizar } from './offline.js';
import { icono, aviso } from './util.js';

import * as login from './vistas/login.js';
import * as registro from './vistas/registro.js';
import * as password from './vistas/password.js';
import * as inicio from './vistas/inicio.js';
import * as crearCuenta from './vistas/crear-cuenta.js';
import * as editarCuenta from './vistas/editar-cuenta.js';
import * as categorias from './vistas/categorias.js';
import * as registrar from './vistas/registrar.js';
import * as transferir from './vistas/transferir.js';
import * as abonar from './vistas/abonar.js';
import * as movimientos from './vistas/movimientos.js';
import * as deudas from './vistas/deudas.js';
import * as metas from './vistas/metas.js';
import * as asistente from './vistas/asistente.js';


const RUTAS = {
  '/login': {
    vista: login,
    publica: true,
    nav: null
  },
  '/registro': {
    vista: registro,
    publica: true,
    nav: null
  },
  '/recuperar-contrasena': {
    vista: password.recuperar,
    publica: true,
    permiteSesion: true,
    nav: null
  },

  '/restablecer-contrasena': {
    vista: password.restablecer,
    publica: true,
    permiteSesion: true,
    nav: null
  },

  '/cambiar-contrasena': {
    vista: password.cambiar,
    nav: null
  },

  '/inicio': {
    vista: inicio,
    nav: 'inicio'
  },
  '/nueva-cuenta': {
    vista: crearCuenta,
    nav: null
  },
  '/editar-cuenta': {
    vista: editarCuenta,
    nav: null
  },
  '/categorias': {
    vista: categorias,
    nav: null
  },
  '/movimientos': {
    vista: movimientos,
    nav: 'inicio'
  },
  '/registrar': {
    vista: registrar,
    nav: null
  },
  '/transferir': {
    vista: transferir,
    nav: null
  },
  '/abonar': {
    vista: abonar,
    nav: null
  },
  '/deudas': {
    vista: deudas,
    nav: 'deudas'
  },
  '/metas': {
    vista: metas,
    nav: 'metas'
  },
  '/asistente': {
    vista: asistente,
    nav: 'asistente'
  }
};


function pintarNav(activa) {
  const nav = document.getElementById('nav');

  if (!activa) {
    nav.hidden = true;
    document.body.classList.remove('con-nav');
    return;
  }

  const item = (id, ruta, texto) => `
    <a
      href="#${ruta}"
      class="nav-item${
        activa === id ? ' activo' : ''
      }"
      ${
        activa === id
          ? 'aria-current="page"'
          : ''
      }
    >
      <span class="nav-icono">
        ${icono(id)}
      </span>
      ${texto}
    </a>
  `;

  nav.innerHTML = `
    ${item('inicio', '/inicio', 'Inicio')}
    ${item('deudas', '/deudas', 'Deudas')}

    <a
      href="#/registrar"
      class="nav-mas"
      aria-label="Registrar movimiento"
    >
      ${icono('mas', 24)}
    </a>

    ${item('metas', '/metas', 'Metas')}
    ${item('asistente', '/asistente', 'Asistente')}
  `;

  nav.hidden = false;
  document.body.classList.add('con-nav');
}


async function navegar() {
  const fragmento =
    location.hash.replace(/^#/, '') || '/inicio';

  const corte = fragmento.indexOf('?');

  const camino = corte < 0
    ? fragmento
    : fragmento.slice(0, corte);

  const consulta = corte < 0
    ? ''
    : fragmento.slice(corte + 1);

  let [, base = 'inicio', parametro] = camino.split('/');

  const ruta = '/' + base;

  if (ruta === '/restablecer-contrasena') {

    const tokens = new URLSearchParams(
      consulta
    ).getAll('token');

    parametro = tokens.length === 1
      ? tokens[0]
      : null;

    // Retirar el secreto de la URL,
    // sin guardarlo localmente.

    history.replaceState(
      null,
      '',
      '#/restablecer-contrasena'
    );
  }
  const definicion = RUTAS[ruta];

  if (!definicion) {
    location.hash = '#/inicio';
    return;
  }

  const autenticada = haySesion();

  if (!definicion.publica && !autenticada) {
    location.hash = '#/login';
    return;
  }

  if (definicion.publica && autenticada && !definicion.permiteSesion) {
    location.hash = '#/inicio';
    return;
  }

  pintarNav(definicion.nav);

  const contenedor = document.createElement('div');
  contenedor.className = 'vista';

  document.getElementById('app')
    .replaceChildren(contenedor);

  window.scrollTo(0, 0);

  try {
    await definicion.vista.render(
      contenedor,
      parametro
    );

  } catch (error) {
    console.error(error);

    const mensaje = document.createElement('p');
    mensaje.className = 'error-general';
    mensaje.textContent = 'No se pudo cargar esta pantalla. Intenta nuevamente.';
    contenedor.replaceChildren(mensaje);
  }
}


async function intentarSincronizar() {
  const resultado = await sincronizar();

  if (!resultado) return;

  if (resultado.sesionCambiada) {
    return;
  }

  if (resultado.errores > 0) {
    aviso(
      'Una operación fue rechazada. ' +
      'Revísala en Movimientos.',
      'alerta'
    );

  } else if (resultado.sincronizadas > 0) {
    aviso(
      `${resultado.sincronizadas} operación(es) ` +
      'sincronizadas correctamente.',
      'ok'
    );
  }

  if (
    resultado.sincronizadas > 0 ||
    resultado.errores > 0
  ) {
    if (
      [
        '#/inicio',
        '#/movimientos',
        '#/deudas'
      ].includes(location.hash)
    ) {
      navegar();
    }
  }
}


// ------------------------------------
// NAVEGACION NORMAL
// ------------------------------------

window.addEventListener(
  'hashchange',
  navegar
);

window.addEventListener('online', () => {
  aviso('Conexión recuperada.');
  intentarSincronizar();
});

window.addEventListener('offline', () => {
  aviso(
    'Sin conexión: las operaciones se ' +
    'guardarán en este dispositivo.',
    'alerta'
  );
});

window.addEventListener(
  'sesion-iniciada',
  intentarSincronizar
);


// ------------------------------------
// CAMBIOS DE SESION EN OTRA PESTAÑA
// ------------------------------------

window.addEventListener('storage', evento => {

  if (
    evento.key !== 'fp:token' &&
    evento.key !== 'fp:usuario'
  ) {
    return;
  }

  // Ocultar inmediatamente cualquier
  // información de la sesión anterior.
  const app = document.getElementById('app');

  if (app) {
    app.replaceChildren();
  }

  pintarNav(null);

  if (!haySesion()) {

    if (location.hash === '#/login') {
      navegar();
    } else {
      location.hash = '#/login';
    }

    return;
  }

  // Otra pestaña terminó de iniciar sesión.
  if (location.hash === '#/inicio') {
    navegar();
  } else {
    location.hash = '#/inicio';
  }
});


// ------------------------------------
// SERVICE WORKER
// ------------------------------------

if ('serviceWorker' in navigator) {
  navigator.serviceWorker
    .register('sw.js')
    .catch(() => {
      // La PWA puede funcionar online
      // aunque falle el Service Worker.
    });
}


// ------------------------------------
// INICIALIZACION
// ------------------------------------

navegar();
intentarSincronizar();
