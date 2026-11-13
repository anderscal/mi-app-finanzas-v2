import { obtenerPlanificacion } from '../api.js';
import { cop, esc, guardarCache } from '../util.js';
import { cargando, errorCarga, pendienteBackend } from './comun.js';

export async function render(c) {
  c.innerHTML = `
    <header class="banda">
      <div class="banda-fila espaciada">
        <h1 class="banda-titulo">Deudas y préstamos</h1>
      </div>
      <div class="totales" id="totales"></div>
    </header>
    <div id="cuerpo">${cargando()}</div>`;

  try {
    const plan = await obtenerPlanificacion();
    guardarCache('planificacion', plan);
    const { obligaciones } = plan;
    const activas = obligaciones.filter((o) => o.estado === 'ACTIVA');
    const suma = (tipo) => activas.filter((o) => o.tipo_obligacion === tipo).reduce((s, o) => s + Number(o.monto_pendiente), 0);
    const cuenta = (tipo) => activas.filter((o) => o.tipo_obligacion === tipo).length;

    c.querySelector('#totales').innerHTML = `
      <div class="total"><span>Debes</span><strong class="monto">${cop(suma('POR_PAGAR'))}</strong><small>${cuenta('POR_PAGAR')} activa(s)</small></div>
      <div class="total"><span>Te deben</span><strong class="monto">${cop(suma('POR_COBRAR'))}</strong><small>${cuenta('POR_COBRAR')} activa(s)</small></div>`;

    const tarjeta = (o) => {
      const original = Number(o.monto_original);
      const abonado = Number(o.total_abonado);
      const pct = original > 0 ? Math.min(100, Math.round((abonado / original) * 100)) : 0;
      const porPagar = o.tipo_obligacion === 'POR_PAGAR';
      return `
        <article class="tarjeta-gris obligacion${o.estado !== 'ACTIVA' ? ' cerrada' : ''}">
          <div class="obl-cabeza"><strong>${esc(o.nombre_obligacion)}</strong><span class="etiqueta">${esc(o.estado)}</span></div>
          <div class="obl-cifra"><span>${porPagar ? 'Lo que debes' : 'Te falta cobrar'}</span><strong class="monto">${cop(o.monto_pendiente)}</strong></div>
          <div class="barra" role="img" aria-label="${pct} % ${porPagar ? 'pagado' : 'cobrado'}"><span style="width:${pct}%"></span></div>
          <div class="resumen-pie"><span>${porPagar ? 'Pagado' : 'Cobrado'} <span class="monto">${cop(abonado)}</span></span><span>de <span class="monto">${cop(original)}</span></span></div>
          ${o.estado === 'ACTIVA' ? `<a class="btn btn-primario btn-chico" href="#/abonar/${o.id_obligacion}">${porPagar ? 'Registrar pago' : 'Registrar cobro'}</a>` : ''}
        </article>`;
    };

    const grupo = (titulo, lista) => lista.length
      ? `<section class="seccion"><div class="seccion-titulo"><h2>${titulo}</h2></div>${lista.map(tarjeta).join('')}</section>`
      : '';

    c.querySelector('#cuerpo').innerHTML =
      (obligaciones.length
        ? grupo('Por pagar', obligaciones.filter((o) => o.tipo_obligacion === 'POR_PAGAR'))
          + grupo('Por cobrar', obligaciones.filter((o) => o.tipo_obligacion === 'POR_COBRAR'))
        : '<section class="seccion"><p class="vacio">No tienes deudas ni préstamos registrados.</p></section>')
      + `<section class="seccion">${pendienteBackend('Crear una deuda o un préstamo nuevo.', 'POST /obligaciones')}</section>`;
  } catch (e) {
    c.querySelector('#cuerpo').innerHTML = `<section class="seccion">${errorCarga(e)}</section>`;
  }
}
