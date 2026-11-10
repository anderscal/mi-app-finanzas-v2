import { obtenerPlanificacion } from '../api.js';
import { cop, esc, nombreMes } from '../util.js';
import { banda, cargando, errorCarga, pendienteBackend } from './comun.js';

export async function render(c) {
  c.innerHTML = `
    ${banda('Presupuestos y metas', { subtitulo: 'Opcionales · te ayudan a planear' })}
    <section class="seccion">
      <div class="seccion-titulo"><h2>Presupuesto mensual</h2></div>
      <div id="presupuestos">${cargando()}</div>
    </section>
    <section class="seccion">
      <div class="seccion-titulo"><h2>Metas de ahorro</h2></div>
      <div id="metas">${cargando()}</div>
    </section>
    <section class="seccion">${pendienteBackend('Crear presupuestos y metas, y abonar a una meta.', 'POST /presupuestos · POST /metas')}</section>`;

  try {
    const { presupuestos, metas } = await obtenerPlanificacion();

    c.querySelector('#presupuestos').innerHTML = presupuestos.length
      ? `<div class="tarjeta-gris lista-presupuestos">${presupuestos.map((p) => {
          const pct = Number(p.porcentaje_usado);
          const alerta = pct >= 90;
          return `
            <div class="presupuesto">
              <div class="presu-cabeza"><strong>${esc(p.categoria)}</strong><span><b class="monto">${cop(p.gastado)}</b> / <span class="monto">${cop(p.monto_limite)}</span></span></div>
              <div class="barra" role="img" aria-label="${pct} % usado"><span class="${alerta ? 'barra-gasto' : ''}" style="width:${Math.min(100, pct)}%"></span></div>
              <span class="${alerta ? 'aviso-limite' : 'presu-pie'}">${alerta ? 'Casi al límite · ' : ''}${Number(p.disponible) >= 0 ? `quedan <span class="monto">${cop(p.disponible)}</span>` : `te pasaste <span class="monto">${cop(-Number(p.disponible))}</span>`} · ${nombreMes(p.mes)} ${p.anio} · ${pct} %</span>
            </div>`;
        }).join('')}</div>`
      : '<p class="vacio">No tienes presupuestos para este mes.</p>';

    c.querySelector('#metas').innerHTML = metas.length
      ? metas.map((m) => {
          const pct = Number(m.porcentaje_progreso);
          return `
            <article class="meta">
              <div class="meta-cabeza"><strong>${esc(m.nombre_meta)}</strong><span class="meta-pct">${Math.round(pct)} %</span></div>
              <div class="barra barra-oscura" role="img" aria-label="${pct} % de la meta"><span style="width:${Math.min(100, pct)}%"></span></div>
              <div class="meta-pie"><span>Ahorrado <span class="monto">${cop(m.monto_acumulado)}</span></span><span>Meta <span class="monto">${cop(m.monto_objetivo)}</span></span></div>
              <button type="button" class="btn btn-oro btn-chico" disabled title="Falta el endpoint en el backend">Abonar a la meta · pronto</button>
            </article>`;
        }).join('')
      : '<p class="vacio">Aún no tienes metas.</p>';
  } catch (e) {
    c.querySelector('#presupuestos').innerHTML = errorCarga(e);
    c.querySelector('#metas').innerHTML = '';
  }
}
