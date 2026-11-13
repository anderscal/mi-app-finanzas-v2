import { obtenerMisCuentas, crearTransferencia, ErrorDeRed } from '../api.js';
import { guardarOffline } from '../offline.js';
import { cop, esc, icono, hoyISO, nuevoUUID, aviso, leerCache } from '../util.js';

const TASA_GMF = 0.004; // la misma que usa el backend (0,4 %)

export async function render(c) {
  // Un uuid por formulario: si el usuario reintenta tras un fallo de red,
  // el backend reconoce la operación y no crea una segunda transferencia.
  const uuidOperacion = nuevoUUID();
  let cuentas = [];

  c.innerHTML = `
    <form id="form-tr" novalidate>
      <header class="banda banda-form">
        <div class="banda-fila">
          <a class="btn-icono" href="#/inicio" aria-label="Volver al inicio">${icono('atras')}</a>
          <h1 class="banda-titulo">Pasar entre mis cuentas</h1>
        </div>
        <div class="monto-grande">
          <label for="tr-monto">Monto a transferir (COP)</label>
          <input id="tr-monto" name="monto" inputmode="numeric" autocomplete="off" placeholder="$ 0" required>
        </div>
      </header>

      <div class="cuerpo-form">
        <div class="par-cuentas">
          <div class="campo">
            <label for="tr-origen">Desde</label>
            <select id="tr-origen" name="origen" required><option value="">Cargando…</option></select>
          </div>
          <button type="button" class="btn-intercambiar" id="tr-cambiar" aria-label="Intercambiar origen y destino">${icono('transferir', 20)}</button>
          <div class="campo">
            <label for="tr-destino">Hacia</label>
            <select id="tr-destino" name="destino" required><option value="">Cargando…</option></select>
          </div>
        </div>
        <div class="campo">
          <label for="tr-fecha">Fecha</label>
          <input id="tr-fecha" name="fecha" type="date" max="${hoyISO()}" value="${hoyISO()}" required>
        </div>
        <div class="campo">
          <label for="tr-motivo">Motivo <span class="opcional">opcional</span></label>
          <input id="tr-motivo" name="motivo" maxlength="150" placeholder="Movimiento interno">
        </div>
        <div class="gmf">
          <div class="gmf-fila">
            <input id="tr-gmf" type="checkbox">
            <label for="tr-gmf">Esta operación generó GMF (4x1000)</label>
          </div>
          <div class="gmf-detalle">
            <div><span>GMF estimado</span><strong class="monto" id="tr-v-gmf">$ 0</strong></div>
            <div><span id="tr-t-sale">Sale de la cuenta origen</span><strong class="monto gasto" id="tr-v-sale">$ 0</strong></div>
            <div><span id="tr-t-entra">Entra a la cuenta destino</span><strong class="monto ingreso" id="tr-v-entra">$ 0</strong></div>
          </div>
        </div>
        <p class="nota">No cuenta como ingreso ni gasto en tu resumen. El GMF es una estimación; algunas transferencias entre cuentas propias están exentas.</p>
        <p class="error-form" id="tr-error" role="alert"></p>
      </div>

      <div class="pie-form">
        <small>Sin conexión se guarda en el celular y se envía después con el mismo identificador.</small>
        <button class="btn btn-primario" type="submit">Confirmar transferencia</button>
      </div>
    </form>`;

  const form = c.querySelector('#form-tr');
  const monto = c.querySelector('#tr-monto');
  const origen = c.querySelector('#tr-origen');
  const destino = c.querySelector('#tr-destino');
  const gmf = c.querySelector('#tr-gmf');
  const error = c.querySelector('#tr-error');

  const valorMonto = () => Number(monto.value.replace(/\D/g, ''));
  const nombre = (id) => cuentas.find((x) => String(x.id_cuenta) === String(id))?.nombre_cuenta || '';

  function recalcular() {
    const m = valorMonto();
    const g = gmf.checked ? Math.round(m * TASA_GMF * 100) / 100 : 0;
    c.querySelector('#tr-v-gmf').textContent = cop(g);
    c.querySelector('#tr-v-sale').textContent = '− ' + cop(m + g);
    c.querySelector('#tr-v-entra').textContent = '+ ' + cop(m);
    c.querySelector('#tr-t-sale').textContent = `Sale de ${nombre(origen.value) || 'la cuenta origen'}`;
    c.querySelector('#tr-t-entra').textContent = `Entra a ${nombre(destino.value) || 'la cuenta destino'}`;
  }

  monto.addEventListener('input', () => {
    const digitos = monto.value.replace(/\D/g, '').slice(0, 13);
    monto.value = digitos ? cop(digitos) : '';
    recalcular();
  });
  [origen, destino, gmf].forEach((el) => el.addEventListener('change', recalcular));
  c.querySelector('#tr-cambiar').addEventListener('click', () => {
    const a = origen.value;
    origen.value = destino.value;
    destino.value = a;
    recalcular();
  });

  try {
    let datos;
    try { datos = await obtenerMisCuentas(); } catch (e) {
      if (!(e instanceof ErrorDeRed) || !leerCache('cuentas')) throw e;
      datos = leerCache('cuentas').datos; // sin conexión: últimas cuentas conocidas
    }
    cuentas = datos.cuentas.filter((x) => x.estado === 'ACTIVA');
    const opciones = cuentas.map((x) => `<option value="${x.id_cuenta}">${esc(x.nombre_cuenta)} · ${cop(x.saldo_actual)}</option>`).join('');
    origen.innerHTML = opciones;
    destino.innerHTML = opciones;
    if (cuentas.length < 2) {
      error.textContent = 'Necesitas al menos dos cuentas activas para transferir.';
      form.querySelector('button[type="submit"]').disabled = true;
    } else {
      destino.value = String(cuentas[1].id_cuenta);
    }
  } catch (e) {
    origen.innerHTML = destino.innerHTML = '<option value="">Sin cuentas</option>';
    error.textContent = e.message;
  }
  recalcular();

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    error.textContent = '';
    const m = valorMonto();
    if (!m) { error.textContent = 'Escribe un monto mayor a cero.'; monto.focus(); return; }
    if (!origen.value || !destino.value) { error.textContent = 'Elige las dos cuentas.'; return; }
    if (origen.value === destino.value) { error.textContent = 'La cuenta de origen y la de destino deben ser diferentes.'; return; }
    if (!form.fecha.value || form.fecha.value > hoyISO()) { error.textContent = 'La fecha no puede ser futura.'; return; }

    // El mismo cuerpo se envía ahora o se guarda para enviarlo después.
    const datos = {
      uuid_operacion: uuidOperacion,
      id_cuenta_origen: Number(origen.value),
      id_cuenta_destino: Number(destino.value),
      monto: m,
      fecha_transferencia: form.fecha.value,
      aplica_gmf: gmf.checked,
    };
    const motivo = form.motivo.value.trim();
    if (motivo) datos.motivo = motivo;

    const boton = form.querySelector('button[type="submit"]');
    boton.disabled = true;
    boton.textContent = 'Transfiriendo…';

    const guardarSinConexion = async () => {
      try {
        await guardarOffline('TRANSFERENCIA', uuidOperacion, datos);
        aviso('Sin conexión: la transferencia quedó guardada en el celular y se enviará después.', 'alerta');
        location.hash = '#/inicio';
      } catch (e) {
        error.textContent = e.message;
        boton.disabled = false;
        boton.textContent = 'Confirmar transferencia';
      }
    };

    if (!navigator.onLine) { await guardarSinConexion(); return; }
    try {
      const r = await crearTransferencia(datos);
      const extra = Number(r.monto_gmf) > 0 ? ` · GMF ${cop(r.monto_gmf)}` : '';
      aviso(`${r.mensaje}${extra}`, 'ok');
      location.hash = '#/inicio';
    } catch (e) {
      if (e instanceof ErrorDeRed) { await guardarSinConexion(); return; }
      error.textContent = e.message;
      boton.disabled = false;
      boton.textContent = 'Confirmar transferencia';
    }
  });
}
