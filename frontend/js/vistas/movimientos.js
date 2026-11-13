import { obtenerHistorialMensual, anularMovimiento } from '../api.js';
import { operacionesLocales, sincronizar, reintentarOperacion, descartarOperacion, esErrorDeDatos, TIPOS_OPERACION } from '../offline.js';
import { cop, esc, icono, nombreMes, fechaCorta, aviso } from '../util.js';
import { cargando, errorCarga } from './comun.js';
import { filaMovimiento } from './inicio.js';

const ORIGEN = { NORMAL: 'Ingreso o gasto', TRANSFERENCIA: 'Transferencia entre cuentas', OBLIGACION: 'Pago o cobro de obligación' };

// Qué hace el backend al anular, según el origen del movimiento.
const EFECTO_ANULAR = {
  NORMAL: 'Se anula solo este movimiento y el saldo de la cuenta se recalcula.',
  TRANSFERENCIA: 'Se anulan la salida y la entrada de la transferencia, incluido el GMF.',
  OBLIGACION: 'Se anula este abono. Si la obligación estaba saldada, vuelve a quedar activa.',
};

export async function render(c) {
  const hoy = new Date();
  const periodo = { anio: hoy.getFullYear(), mes: hoy.getMonth() + 1 };
  let movimientos = [];

  c.innerHTML = `
    <header class="banda">
      <div class="banda-fila">
        <a class="btn-icono" href="#/inicio" aria-label="Volver al inicio">${icono('atras')}</a>
        <h1 class="banda-titulo">Movimientos</h1>
      </div>
      <div class="selector-mes">
        <button type="button" class="btn-icono" id="mes-ant" aria-label="Mes anterior">${icono('atras')}</button>
        <strong id="mes-texto"></strong>
        <button type="button" class="btn-icono girar" id="mes-sig" aria-label="Mes siguiente">${icono('atras')}</button>
      </div>
    </header>
    <section class="seccion" id="cola"></section>
    <section class="seccion">
      <div class="seccion-titulo"><h2>Registrados</h2><small class="pista">Toca uno para ver el detalle</small></div>
      <div id="lista">${cargando()}</div>
    </section>
    <dialog id="detalle" class="hoja" aria-labelledby="detalle-titulo"></dialog>`;

  const dialogo = c.querySelector('#detalle');
  const esMesActual = () => periodo.anio === hoy.getFullYear() && periodo.mes === hoy.getMonth() + 1;

  async function pintar() {
    c.querySelector('#mes-texto').textContent = `${nombreMes(periodo.mes)} ${periodo.anio}`;
    c.querySelector('#mes-sig').disabled = esMesActual();
    const caja = c.querySelector('#lista');
    caja.innerHTML = cargando();
    try {
      const h = await obtenerHistorialMensual(periodo.anio, periodo.mes);
      movimientos = h.movimientos;
      caja.innerHTML = movimientos.length
        ? `<div class="lista">${movimientos.map((m) => filaMovimiento(m, { accionable: true })).join('')}</div>`
        : '<p class="vacio">No hay movimientos en este mes.</p>';
    } catch (e) {
      caja.innerHTML = errorCarga(e);
    }
  }

  function abrirDetalle(m) {
    const esGasto = m.tipo === 'GASTO';
    const activo = m.estado === 'ACTIVO';
    const filas = [
      ['Tipo', esGasto ? 'Gasto (sale dinero)' : 'Ingreso (entra dinero)'],
      ['Origen', ORIGEN[m.origen] || m.origen],
      ['Cuenta', m.nombre_cuenta],
      m.nombre_categoria ? ['Categoría', m.nombre_categoria] : null,
      ['Fecha', fechaCorta(m.fecha_movimiento) + ' ' + m.fecha_movimiento.slice(0, 4)],
      Number(m.monto_gmf) > 0 ? ['GMF (4x1000)', cop(m.monto_gmf)] : null,
      ['Estado', activo ? 'Activo' : 'Anulado'],
    ].filter(Boolean);

    dialogo.innerHTML = `
      <div class="hoja-cabeza">
        <h2 id="detalle-titulo">${esc(m.descripcion || m.nombre_categoria || 'Movimiento')}</h2>
        <button type="button" class="btn-icono cerrar" data-cerrar aria-label="Cerrar">${icono('mas', 20)}</button>
      </div>
      <p class="hoja-monto ${esGasto ? 'gasto' : 'ingreso'} monto">${esGasto ? '− ' : '+ '}${cop(m.monto)}</p>
      <dl class="hoja-datos">${filas.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
      ${activo ? `
        <div id="zona-anular">
          <button type="button" class="btn btn-peligro" id="btn-anular">Anular movimiento</button>
        </div>` : '<p class="vacio">Este movimiento ya está anulado y no afecta tus saldos.</p>'}
      <p class="error-form" id="detalle-error" role="alert"></p>`;

    dialogo.querySelector('[data-cerrar]').addEventListener('click', () => dialogo.close());
    const btn = dialogo.querySelector('#btn-anular');
    if (btn) {
      btn.addEventListener('click', () => {
        // Segundo paso: confirmar dentro de la misma hoja (sin confirm() del navegador).
        dialogo.querySelector('#zona-anular').innerHTML = `
          <div class="confirmar">
            <strong>¿Anular este movimiento?</strong>
            <span>${esc(EFECTO_ANULAR[m.origen] || '')} No se puede deshacer.</span>
            <div class="confirmar-botones">
              <button type="button" class="btn btn-secundario btn-chico" data-cerrar>Cancelar</button>
              <button type="button" class="btn btn-peligro btn-chico" id="btn-si">Sí, anular</button>
            </div>
          </div>`;
        dialogo.querySelector('.confirmar [data-cerrar]').addEventListener('click', () => dialogo.close());
        dialogo.querySelector('#btn-si').addEventListener('click', async (ev) => {
          ev.target.disabled = true;
          ev.target.textContent = 'Anulando…';
          try {
            const r = await anularMovimiento(m.id_movimiento);
            dialogo.close();
            aviso(r.mensaje, 'ok');
            pintar();
          } catch (e) {
            dialogo.querySelector('#detalle-error').textContent = e.message;
            ev.target.disabled = false;
            ev.target.textContent = 'Sí, anular';
          }
        });
      });
    }
    dialogo.showModal();
  }

  c.querySelector('#lista').addEventListener('click', (ev) => {
    const fila = ev.target.closest('.movimiento.accionable');
    if (!fila) return;
    const m = movimientos.find((x) => String(x.id_movimiento) === fila.dataset.id);
    if (m) abrirDetalle(m);
  });
  dialogo.addEventListener('click', (ev) => { if (ev.target === dialogo) dialogo.close(); });

  c.querySelector('#mes-ant').addEventListener('click', () => {
    periodo.mes -= 1;
    if (periodo.mes === 0) { periodo.mes = 12; periodo.anio -= 1; }
    pintar();
  });
  c.querySelector('#mes-sig').addEventListener('click', () => {
    if (esMesActual()) return;
    periodo.mes += 1;
    if (periodo.mes === 13) { periodo.mes = 1; periodo.anio += 1; }
    pintar();
  });

  c.addEventListener('refrescar', () => pintar());
  await pintarCola(c);
  await pintar();
}

// Operaciones guardadas en el celular que aún no llegan al backend.
// Se envían en orden; si una es rechazada, la cola se detiene ahí
// hasta que el usuario la reintente o la descarte.
function resumenOperacion(op) {
  const d = op.datos || {};
  if (op.tipo_operacion === 'TRANSFERENCIA') {
    return { titulo: d.motivo || 'Transferencia', signo: '', clase: 'neutro', monto: d.monto };
  }
  const esGasto = op.tipo_operacion === 'MOVIMIENTO_NORMAL' ? d.tipo === 'GASTO' : null;
  if (op.tipo_operacion === 'ABONO_OBLIGACION') {
    return { titulo: d.descripcion || 'Abono a obligación', signo: '', clase: 'neutro', monto: d.monto };
  }
  return { titulo: d.descripcion || (esGasto ? 'Gasto' : 'Ingreso'), signo: esGasto ? '− ' : '+ ', clase: esGasto ? 'gasto' : 'ingreso', monto: d.monto };
}

async function pintarCola(c) {
  const caja = c.querySelector('#cola');
  const lista = await operacionesLocales();
  if (!lista.length) { caja.hidden = true; caja.innerHTML = ''; return; }
  const hayError = lista.some((op) => op.estado_sync === 'ERROR');
  caja.hidden = false;
  caja.innerHTML = `
    <div class="seccion-titulo"><h2>En este celular</h2><button type="button" class="enlace" id="btn-sync">Enviar ahora</button></div>
    ${hayError ? '<p class="aviso-cola">Una operación fue rechazada. Las siguientes esperan hasta que la reintentes o la descartes, porque pueden depender de ella.</p>' : ''}
    <div class="lista">${lista.map((op) => {
      const r = resumenOperacion(op);
      const error = op.estado_sync === 'ERROR';
      const fecha = op.datos?.fecha_movimiento || op.datos?.fecha_transferencia;
      return `
      <article class="movimiento pendiente-local${error ? ' con-error' : ''}">
        <span class="mov-icono ${error ? 'gasto' : 'neutro'}" aria-hidden="true">${icono('nube', 19)}</span>
        <div class="mov-texto">
          <strong>${esc(r.titulo)}</strong>
          <span>${esc(TIPOS_OPERACION[op.tipo_operacion] || op.tipo_operacion)}${fecha ? ' · ' + fechaCorta(fecha) : ''}</span>
          <span>${error ? `Rechazada · ${esc(op.ultimo_error || '')}` : op.ultimo_error ? `Pendiente · ${esc(op.ultimo_error)}` : 'Pendiente de enviar'}</span>
          ${error ? `<span class="acciones-op">
            <button type="button" class="enlace" data-reintentar="${esc(op.uuid_operacion)}" ${esErrorDeDatos(op) ? 'disabled title="Datos inválidos: reenviarlos igual no sirve"' : ''}>Reintentar</button>
            <button type="button" class="enlace peligro" data-descartar="${esc(op.uuid_operacion)}">Descartar</button>
          </span>
          <span class="confirmar-descarte" data-confirmar="${esc(op.uuid_operacion)}" hidden>
            Solo se borra la copia del celular; no anula nada en el servidor.
            <button type="button" class="enlace peligro" data-si="${esc(op.uuid_operacion)}">Sí, descartar</button>
          </span>` : ''}
        </div>
        <span class="mov-monto ${r.clase} monto">${r.signo}${cop(r.monto)}</span>
      </article>`;
    }).join('')}</div>`;

  caja.querySelector('#btn-sync').addEventListener('click', async () => {
    const r = await sincronizar();
    if (!r) aviso('No se pudo enviar ahora. Revisa la conexión.', 'alerta');
    else if (r.errores) aviso('Hay una operación rechazada: revísala antes de seguir.', 'alerta');
    else if (r.sincronizadas) aviso(`${r.sincronizadas} operación(es) enviadas`, 'ok');
    else if (r.pendientes) aviso(r.mensajes[r.mensajes.length - 1] || 'Siguen pendientes.', 'alerta');
    await pintarCola(c);
    if (r && r.sincronizadas) c.dispatchEvent(new Event('refrescar'));
  });
  caja.querySelectorAll('[data-reintentar]').forEach((b) => b.addEventListener('click', async () => {
    await reintentarOperacion(b.dataset.reintentar);
    aviso('Lista para reenviar con el mismo identificador.');
    await pintarCola(c);
  }));
  caja.querySelectorAll('[data-descartar]').forEach((b) => b.addEventListener('click', () => {
    caja.querySelector(`[data-confirmar="${CSS.escape(b.dataset.descartar)}"]`).hidden = false;
  }));
  caja.querySelectorAll('[data-si]').forEach((b) => b.addEventListener('click', async () => {
    await descartarOperacion(b.dataset.si);
    aviso('Copia local descartada');
    await pintarCola(c);
  }));
}
