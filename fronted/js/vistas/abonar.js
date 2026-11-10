import { obtenerMisCuentas, obtenerPlanificacion, registrarAbono, ErrorDeRed } from '../api.js';
import { guardarOffline } from '../offline.js';
import { cop, esc, icono, hoyISO, nuevoUUID, aviso, leerCache, guardarCache } from '../util.js';

// Pantalla de pago (deuda POR_PAGAR) o cobro (préstamo POR_COBRAR).
// Ruta: #/abonar/<id_obligacion>
export async function render(c, idObligacion) {
  const uuidLocal = nuevoUUID(); // un uuid por formulario: reintentar no duplica el abono
  const id = Number(idObligacion);

  let obligacion = null;
  try {
    const plan = await obtenerPlanificacion();
    guardarCache('planificacion', plan);
    obligacion = plan.obligaciones.find((o) => o.id_obligacion === id) || null;
  } catch {
    // Sin conexión: se usa la última planificación conocida, si existe.
    const cache = leerCache('planificacion');
    obligacion = cache?.datos?.obligaciones?.find((o) => o.id_obligacion === id) || null;
  }

  if (obligacion && obligacion.estado !== 'ACTIVA') {
    c.innerHTML = `
      <header class="banda"><div class="banda-fila"><a class="btn-icono" href="#/deudas" aria-label="Volver">${icono('atras')}</a><h1 class="banda-titulo">${esc(obligacion.nombre_obligacion)}</h1></div></header>
      <section class="seccion"><p class="vacio">Esta obligación está ${esc(obligacion.estado.toLowerCase())}. No admite más abonos.</p></section>`;
    return;
  }

  const porPagar = !obligacion || obligacion.tipo_obligacion === 'POR_PAGAR';
  const verbo = porPagar ? 'pago' : 'cobro';
  const pendiente = obligacion ? Number(obligacion.monto_pendiente) : null;

  c.innerHTML = `
    <form id="form-ab" novalidate>
      <header class="banda banda-form${porPagar ? '' : ' banda-oscura'}">
        <div class="banda-fila">
          <a class="btn-icono" href="#/deudas" aria-label="Volver a deudas">${icono('atras')}</a>
          <h1 class="banda-titulo">Registrar ${verbo}</h1>
        </div>
        <p class="banda-sub">${obligacion ? `${esc(obligacion.nombre_obligacion)} · ${porPagar ? 'debes' : 'te deben'} <span class="monto">${cop(pendiente)}</span>` : `Obligación #${id}`}</p>
        <div class="monto-grande">
          <label for="ab-monto">${porPagar ? '¿Cuánto vas a pagar?' : '¿Cuánto te devolvieron?'} (COP)</label>
          <input id="ab-monto" name="monto" inputmode="numeric" autocomplete="off" placeholder="$ 0" required>
        </div>
        ${pendiente ? `<button type="button" class="chip chip-banda" id="ab-todo">${porPagar ? 'Pagar todo' : 'Cobrar todo'} · ${cop(pendiente)}</button>` : ''}
      </header>

      <div class="cuerpo-form">
        <div class="campo">
          <label for="ab-cuenta">${porPagar ? 'Pagar desde' : 'Recibir en'}</label>
          <select id="ab-cuenta" name="cuenta" required><option value="">Cargando…</option></select>
        </div>
        <div class="campo">
          <label for="ab-fecha">Fecha</label>
          <input id="ab-fecha" name="fecha" type="date" max="${hoyISO()}" value="${hoyISO()}" required>
        </div>
        <div class="campo">
          <label for="ab-desc">Descripción <span class="opcional">opcional</span></label>
          <input id="ab-desc" name="descripcion" maxlength="255" placeholder="${porPagar ? 'Ej. cuota de noviembre' : 'Ej. abono en efectivo'}">
        </div>
        <div class="resumen-abono" id="ab-resumen" ${pendiente ? '' : 'hidden'}>
          <div><span>Pendiente ahora</span><strong class="monto">${cop(pendiente)}</strong></div>
          <div><span>Este ${verbo}</span><strong class="monto ${porPagar ? 'gasto' : 'ingreso'}" id="ab-v-monto">$ 0</strong></div>
          <div class="total-abono"><span>Quedará pendiente</span><strong class="monto" id="ab-v-queda">${cop(pendiente)}</strong></div>
        </div>
        <p class="nota">${porPagar ? 'El pago sale de tu cuenta, pero no cuenta como gasto ordinario en tu resumen.' : 'El cobro entra a tu cuenta, pero no cuenta como ingreso ordinario en tu resumen.'} Si el pendiente llega a cero, la obligación queda saldada.</p>
        <p class="error-form" id="ab-error" role="alert"></p>
      </div>

      <div class="pie-form">
        <small>Sin conexión se guarda en el celular y se envía después.</small>
        <button class="btn btn-primario" type="submit">Registrar ${verbo}</button>
      </div>
    </form>`;

  const form = c.querySelector('#form-ab');
  const monto = c.querySelector('#ab-monto');
  const cuenta = c.querySelector('#ab-cuenta');
  const error = c.querySelector('#ab-error');
  const valor = () => Number(monto.value.replace(/\D/g, ''));

  function recalcular() {
    if (!pendiente) return;
    const m = valor();
    c.querySelector('#ab-v-monto').textContent = (porPagar ? '− ' : '+ ') + cop(m);
    const queda = pendiente - m;
    const el = c.querySelector('#ab-v-queda');
    el.textContent = queda === 0 ? '$ 0 · saldada' : cop(queda);
    el.classList.toggle('gasto', queda < 0);
  }

  monto.addEventListener('input', () => {
    const d = monto.value.replace(/\D/g, '').slice(0, 13);
    monto.value = d ? cop(d) : '';
    recalcular();
  });
  c.querySelector('#ab-todo')?.addEventListener('click', () => {
    monto.value = cop(pendiente);
    recalcular();
  });

  try {
    let datos;
    try { datos = await obtenerMisCuentas(); } catch (e) {
      if (!(e instanceof ErrorDeRed) || !leerCache('cuentas')) throw e;
      datos = leerCache('cuentas').datos;
    }
    const activas = datos.cuentas.filter((x) => x.estado === 'ACTIVA');
    cuenta.innerHTML = activas.length
      ? activas.map((x) => `<option value="${x.id_cuenta}">${esc(x.nombre_cuenta)} · ${cop(x.saldo_actual)}</option>`).join('')
      : '<option value="">No tienes cuentas activas</option>';
  } catch (e) {
    cuenta.innerHTML = '<option value="">Sin cuentas</option>';
    error.textContent = e.message;
  }

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    error.textContent = '';
    const m = valor();
    if (!m) { error.textContent = 'Escribe un monto mayor a cero.'; monto.focus(); return; }
    if (pendiente !== null && m > pendiente) { error.textContent = `El ${verbo} no puede superar lo pendiente (${cop(pendiente)}).`; return; }
    if (!cuenta.value) { error.textContent = 'Elige una cuenta.'; return; }
    if (!form.fecha.value || form.fecha.value > hoyISO()) { error.textContent = 'La fecha no puede ser futura.'; return; }

    const datos = {
      uuid_local: uuidLocal,
      id_cuenta: Number(cuenta.value),
      id_obligacion: id,
      monto: m,
      fecha_movimiento: form.fecha.value,
      descripcion: form.descripcion.value.trim() || null,
    };

    const boton = form.querySelector('button[type="submit"]');
    boton.disabled = true;
    boton.textContent = 'Registrando…';

    const guardarSinConexion = async () => {
      try {
        await guardarOffline('ABONO_OBLIGACION', uuidLocal, datos);
        aviso(`Sin conexión: el ${verbo} quedó guardado en el celular y se enviará después.`, 'alerta');
        location.hash = '#/deudas';
      } catch (e) {
        error.textContent = e.message;
        boton.disabled = false;
        boton.textContent = `Registrar ${verbo}`;
      }
    };

    if (!navigator.onLine) { await guardarSinConexion(); return; }
    try {
      const r = await registrarAbono(datos);
      const queda = Number(r.monto_pendiente);
      aviso(queda === 0
        ? `${porPagar ? '¡Deuda saldada!' : '¡Préstamo cobrado por completo!'}`
        : `${r.mensaje} · quedan ${cop(queda)}`, 'ok');
      location.hash = '#/deudas';
    } catch (e) {
      if (e instanceof ErrorDeRed) { await guardarSinConexion(); return; }
      error.textContent = e.message;
      boton.disabled = false;
      boton.textContent = `Registrar ${verbo}`;
    }
  });
}
