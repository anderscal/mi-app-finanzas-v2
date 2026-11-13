import { obtenerMisCuentas, obtenerResumenMensual, obtenerHistorialMensual, ErrorDeRed } from '../api.js';
import { obtenerUsuario, cerrarSesion } from '../sesion.js';
import { operacionesLocales } from '../offline.js';
import { cop, esc, icono, fechaCorta, nombreMes, guardarCache, leerCache } from '../util.js';
import { cargando, errorCarga } from './comun.js';

const INICIALES_TIPO = { AHORROS: 'Ahorros', CORRIENTE: 'Corriente', EFECTIVO: 'Efectivo' };

function saldosOcultos() {
  try { return localStorage.getItem('fp:ocultar') === '1'; } catch { return false; }
}

export async function render(c) {
  const usuario = obtenerUsuario() || {};
  const iniciales = ((usuario.nombre_1 || '?')[0] + (usuario.apellido_1 || '')[0]).toUpperCase();
  const hoy = new Date();
  const anio = hoy.getFullYear();
  const mes = hoy.getMonth() + 1;

  c.innerHTML = `
    <header class="banda banda-inicio">
      <div class="banda-fila espaciada">
        <span class="avatar" aria-hidden="true">${esc(iniciales)}</span>
        <div class="banda-acciones">
          <button type="button" class="btn-icono" id="btn-ocultar" aria-label="Ocultar o mostrar saldos">${icono('ojo')}</button>
          <button type="button" class="btn-icono" id="btn-salir" aria-label="Cerrar sesión">${icono('salir')}</button>
        </div>
      </div>
      <p class="saludo">Hola, ${esc(usuario.nombre_1 || '')}</p>
      <div class="saldo-general">
        <span class="saldo-etiqueta">Saldo general disponible</span>
        <span class="saldo-valor monto" id="saldo-general">…</span>
        <div class="saldo-meta">
          <a class="pildora-oro" id="pendientes" href="#/movimientos" hidden></a>
          <span id="saldo-detalle"></span>
        </div>
      </div>
    </header>

    <nav class="acciones" aria-label="Acciones rápidas">
      <a href="#/registrar" class="accion"><span class="accion-circulo lleno">${icono('mas', 26)}</span>Registrar</a>
      <a href="#/transferir" class="accion"><span class="accion-circulo lleno">${icono('transferir', 24)}</span>Transferir</a>
      <a href="#/deudas" class="accion"><span class="accion-circulo">${icono('deudas', 24)}</span>Deudas</a>
      <a href="#/metas" class="accion"><span class="accion-circulo">${icono('metas', 24)}</span>Metas</a>
    </nav>

    
<section class="seccion">

  <div class="seccion-titulo">
    <h2>Mis cuentas</h2>

    <a href="#/nueva-cuenta">
      + Nueva cuenta
    </a>
  </div>

  <div class="cuentas" id="cuentas">
    ${cargando()}
  </div>

</section>

<section class="seccion">

  <div class="seccion-titulo">
    <h2>Categorías financieras</h2>

    <a href="#/categorias">
      Administrar
    </a>
  </div>

  <p class="nota">
    Organiza tus ingresos y gastos
    mediante categorías personalizadas.
  </p>

</section>


    <section class="seccion">
      <div class="tarjeta-gris" id="resumen">
        <div class="seccion-titulo"><h2>Resumen de ${nombreMes(mes)}</h2></div>
        <div id="resumen-cuerpo">${cargando()}</div>
      </div>
    </section>

    <section class="seccion">
      <div class="seccion-titulo"><h2>Últimos movimientos</h2><a href="#/movimientos">Ver todos</a></div>
      <div id="ultimos">${cargando()}</div>
    </section>`;

  if (saldosOcultos()) c.classList.add('ocultar-montos');
  c.querySelector('#btn-ocultar').addEventListener('click', () => {
    const ocultar = !c.classList.contains('ocultar-montos');
    c.classList.toggle('ocultar-montos', ocultar);
    try { localStorage.setItem('fp:ocultar', ocultar ? '1' : '0'); } catch { /* nada */ }
  });
  c.querySelector('#btn-salir').addEventListener('click', () => {
    cerrarSesion();
    location.hash = '#/login';
  });

  // Las tres cargas van en paralelo; cada una pinta su sección.
  pintarPendientes(c);
  pintarCuentas(c);
  pintarResumen(c, anio, mes);
  pintarUltimos(c, anio, mes);
}

async function pintarPendientes(c) {
  const lista = await operacionesLocales();
  const el = c.querySelector('#pendientes');
  if (!lista.length) return;
  const errores = lista.filter((p) => p.estado_sync === 'ERROR').length;
  el.textContent = errores ? `${errores} rechazada(s) · revisar` : `${lista.length} sin sincronizar`;
  el.hidden = false;
}

async function pintarCuentas(c) {
  const caja = c.querySelector('#cuentas');
  let datos;
  let desdeCache = false;
  try {
    datos = await obtenerMisCuentas();
    guardarCache('cuentas', datos);
  } catch (e) {
    const cache = leerCache('cuentas');
    if (e instanceof ErrorDeRed && cache) {
      datos = cache.datos;
      desdeCache = new Date(cache.en);
    } else {
      caja.innerHTML = errorCarga(e);
      c.querySelector('#saldo-general').textContent = '—';
      return;
    }
  }

  c.querySelector('#saldo-general').textContent = cop(datos.saldo_general);
  c.querySelector('#saldo-detalle').textContent = desdeCache
    ? `Sin conexión · datos de las ${desdeCache.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })}`
    : `${datos.total_cuentas} cuenta(s) · COP`;


  if (!datos.cuentas.length) {

    caja.innerHTML = `
    <div class="vacio">
      <p>Aún no tienes cuentas financieras.</p>

      <a href="#/nueva-cuenta">
        Crear mi primera cuenta
      </a>
    </div>
  `;

    return;
  }

  caja.innerHTML = datos.cuentas.map((cu) => `
    <article class="cuenta${cu.estado !== 'ACTIVA' ? ' inactiva' : ''}">
      <span class="cuenta-inicial" aria-hidden="true">${cu.tipo_cuenta === 'EFECTIVO' ? '$' : esc(cu.nombre_cuenta[0])}</span>
      <div class="cuenta-nombre"><strong>${esc(cu.nombre_cuenta)}</strong><span>${INICIALES_TIPO[cu.tipo_cuenta] || esc(cu.tipo_cuenta)}${cu.estado !== 'ACTIVA' ? ' · inactiva' : ''}</span></div>
      <span class="cuenta-saldo monto">${cop(cu.saldo_actual)}</span>

${cu.estado === 'ACTIVA'
      ? `
    <a
      class="enlace"
      href="#/editar-cuenta/${Number(cu.id_cuenta)}"
    >
      Editar cuenta
    </a>
  `
      : `
    <span class="pista">
      Cuenta desactivada
    </span>
  `
    }

    </article>`).join('');
}

async function pintarResumen(c, anio, mes) {
  const caja = c.querySelector('#resumen-cuerpo');
  try {
    const r = await obtenerResumenMensual(anio, mes);
    const ingresos = Number(r.ingresos_ordinarios);
    const gastos = Number(r.gastos_ordinarios);
    const pct = ingresos > 0 ? Math.min(100, Math.round((gastos / ingresos) * 100)) : 0;
    caja.innerHTML = `
      <div class="resumen-cifras">
        <div class="mini"><span>Ingresos</span><strong class="ingreso monto">${cop(ingresos)}</strong></div>
        <div class="mini"><span>Gastos</span><strong class="gasto monto">${cop(gastos)}</strong></div>
      </div>
      <div class="barra" role="img" aria-label="Gastaste el ${pct} % de tus ingresos"><span class="barra-gasto" style="width:${pct}%"></span></div>
      <div class="resumen-pie"><span>Gastaste el ${pct} % de tus ingresos</span><span>GMF <span class="monto">${cop(r.gmf_total)}</span></span></div>`;
  } catch (e) {
    caja.innerHTML = errorCarga(e);
  }
}

// opciones.accionable: la fila es un botón que abre el detalle (pantalla Movimientos).
export function filaMovimiento(m, opciones) {
  const accionable = Boolean(opciones && opciones.accionable === true);
  const esGasto = m.tipo === 'GASTO';
  const interno = m.origen !== 'NORMAL';
  const clase = interno ? 'neutro' : esGasto ? 'gasto' : 'ingreso';
  const icon = m.origen === 'TRANSFERENCIA' ? 'transferir' : m.origen === 'OBLIGACION' ? 'deudas' : esGasto ? 'comida' : 'maletin';
  const detalle = [
    m.origen === 'NORMAL' ? m.nombre_categoria : m.origen === 'TRANSFERENCIA' ? 'Transferencia' : 'Obligación',
    m.nombre_cuenta,
    fechaCorta(m.fecha_movimiento),
  ].filter(Boolean).map(esc).join(' · ');
  const signo = esGasto ? '− ' : '+ ';
  const abre = accionable
    ? `<button type="button" class="movimiento accionable${m.estado === 'ANULADO' ? ' anulado' : ''}" data-id="${m.id_movimiento}">`
    : `<article class="movimiento${m.estado === 'ANULADO' ? ' anulado' : ''}">`;
  return `
    ${abre}
      <span class="mov-icono ${clase}" aria-hidden="true">${icono(icon, 19)}</span>
      <span class="mov-texto"><strong>${esc(m.descripcion || m.nombre_categoria || 'Movimiento')}</strong><span>${detalle}${m.estado === 'ANULADO' ? ' · anulado' : ''}</span></span>
      <span class="mov-monto ${clase} monto">${signo}${cop(m.monto)}</span>
    ${accionable ? '</button>' : '</article>'}`;
}

async function pintarUltimos(c, anio, mes) {
  const caja = c.querySelector('#ultimos');
  try {
    const h = await obtenerHistorialMensual(anio, mes);
    const lista = h.movimientos.slice(0, 5);
    caja.innerHTML = lista.length
      ? `<div class="lista">${lista.map(filaMovimiento).join('')}</div>`
      : '<p class="vacio">Sin movimientos este mes.</p>';
  } catch (e) {
    caja.innerHTML = errorCarga(e);
  }
}
