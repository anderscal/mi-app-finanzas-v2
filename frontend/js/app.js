// Punto de entrada: rutas por hash, barra de navegación y sincronización offline.

import { haySesion } from './sesion.js';
import { sincronizar } from './offline.js';
import { icono, aviso } from './util.js';

import * as login from './vistas/login.js';
import * as registro from './vistas/registro.js';
import * as inicio from './vistas/inicio.js';
import * as crearCuenta from './vistas/crear-cuenta.js';
import * as editarCuenta from './vistas/editar-cuenta.js';
import * as registrar from './vistas/registrar.js';
import * as transferir from './vistas/transferir.js';
import * as abonar from './vistas/abonar.js';
import * as movimientos from './vistas/movimientos.js';
import * as deudas from './vistas/deudas.js';
import * as metas from './vistas/metas.js';
import * as asistente from './vistas/asistente.js';
import * as categorias from './vistas/categorias.js';

// publica: no exige sesión. nav: pestaña activa (null = sin barra inferior).
const RUTAS = {
  '/login': { vista: login, publica: true, nav: null },
  '/registro': { vista: registro, publica: true, nav: null },
  '/inicio': { vista: inicio, nav: 'inicio' },
  '/nueva-cuenta': { vista: crearCuenta, nav: null },
  '/editar-cuenta': { vista: editarCuenta, nav: null },
  '/movimientos': { vista: movimientos, nav: 'inicio' },
  '/registrar': { vista: registrar, nav: null },
  '/transferir': { vista: transferir, nav: null },
  '/abonar': { vista: abonar, nav: null }, // #/abonar/<id_obligacion>
  '/deudas': { vista: deudas, nav: 'deudas' },
  '/metas': { vista: metas, nav: 'metas' },
  '/asistente': { vista: asistente, nav: 'asistente' },
  '/categorias': {
    vista: categorias,
    nav: null
  },

};

function pintarNav(activa) {
  const nav = document.getElementById('nav');
  if (!activa) {
    nav.hidden = true;
    document.body.classList.remove('con-nav');
    return;
  }
  const item = (id, ruta, texto) => `
    <a href="#${ruta}" class="nav-item${activa === id ? ' activo' : ''}"${activa === id ? ' aria-current="page"' : ''}>
      <span class="nav-icono">${icono(id)}</span>${texto}
    </a>`;
  nav.innerHTML = `
    ${item('inicio', '/inicio', 'Inicio')}
    ${item('deudas', '/deudas', 'Deudas')}
    <a href="#/registrar" class="nav-mas" aria-label="Registrar movimiento">${icono('mas', 24)}</a>
    ${item('metas', '/metas', 'Metas')}
    ${item('asistente', '/asistente', 'Asistente')}`;
  nav.hidden = false;
  document.body.classList.add('con-nav');
}

async function navegar() {
  // "#/abonar/3" → ruta "/abonar", parámetro "3"
  const [, base = 'inicio', parametro] = (location.hash.replace(/^#/, '') || '/inicio').split('/');
  const ruta = '/' + base;
  const def = RUTAS[ruta];
  if (!def) { location.hash = '#/inicio'; return; }
  if (!def.publica && !haySesion()) { location.hash = '#/login'; return; }
  if (def.publica && haySesion()) { location.hash = '#/inicio'; return; }

  pintarNav(def.nav);

  // Un contenedor nuevo por navegación: si una carga lenta termina
  // después de cambiar de pantalla, escribe en un nodo que ya no está.
  const contenedor = document.createElement('div');
  contenedor.className = 'vista';
  document.getElementById('app').replaceChildren(contenedor);
  window.scrollTo(0, 0);
  try {
    await def.vista.render(contenedor, parametro);
  } catch (e) {
    console.error(e);
    contenedor.innerHTML = `<p class="error-general">No se pudo cargar esta pantalla. ${e.message || ''}</p>`;
  }
}

async function intentarSincronizar() {
  const r = await sincronizar();
  if (!r) return;
  if (r.errores > 0) {
    aviso('Una operación guardada sin conexión fue rechazada. Revísala en Movimientos.', 'alerta');
  } else if (r.sincronizadas > 0) {
    aviso(`${r.sincronizadas} operación(es) guardadas sin conexión se enviaron`, 'ok');
  }
  if (r.sincronizadas > 0 || r.errores > 0) {
    if (['#/inicio', '#/movimientos', '#/deudas'].includes(location.hash)) navegar();
  }
}

window.addEventListener('hashchange', navegar);
window.addEventListener('online', () => { aviso('Conexión recuperada'); intentarSincronizar(); });
window.addEventListener('offline', () => aviso('Sin conexión: lo que registres se guarda en el celular y se envía después', 'alerta'));
window.addEventListener('sesion-iniciada', intentarSincronizar);

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(() => { /* sin modo offline del shell */ });
}

navegar();
intentarSincronizar();
