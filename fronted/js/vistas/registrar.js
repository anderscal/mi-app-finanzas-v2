import { obtenerMisCuentas, obtenerCategorias, crearMovimientoNormal, ErrorDeRed } from '../api.js';
import { guardarOffline } from '../offline.js';
import { cop, esc, icono, hoyISO, nuevoUUID, aviso, leerCache } from '../util.js';

export async function render(c) {
  const estado = { tipo: 'GASTO', categoria: null };

  c.innerHTML = `
    <form id="form-mov" novalidate>
      <header class="banda banda-form" id="banda-mov">
        <div class="banda-fila">
          <a class="btn-icono" href="#/inicio" aria-label="Volver al inicio">${icono('atras')}</a>
          <h1 class="banda-titulo">Nuevo movimiento</h1>
        </div>
        <div class="segmento" role="group" aria-label="Tipo de movimiento">
          <button type="button" data-tipo="GASTO" aria-pressed="true">Gasto</button>
          <button type="button" data-tipo="INGRESO" aria-pressed="false">Ingreso</button>
        </div>
        <div class="monto-grande">
          <label for="mov-monto">¿Cuánto fue? (COP)</label>
          <input id="mov-monto" name="monto" inputmode="numeric" autocomplete="off" placeholder="$ 0" required>
        </div>
      </header>

      <div class="cuerpo-form">
        <div class="campo">
          <label for="mov-cuenta">Cuenta</label>
          <select id="mov-cuenta" name="cuenta" required><option value="">Cargando cuentas…</option></select>
        </div>
        <div class="campo">
          <label for="mov-fecha">Fecha</label>
          <input id="mov-fecha" name="fecha" type="date" max="${hoyISO()}" value="${hoyISO()}" required>
        </div>
        <fieldset class="campo">
          <legend>Categoría</legend>
          <div class="chips" id="chips"></div>
        </fieldset>
        <div class="campo">
          <label for="mov-desc">Descripción <span class="opcional">opcional</span></label>
          <input id="mov-desc" name="descripcion" maxlength="255" placeholder="Ej. almuerzo con el equipo">
        </div>
        <div class="gmf" id="gmf">
          <div class="gmf-fila">
            <input id="mov-gmf" type="checkbox" disabled>
            <label for="mov-gmf">Esta operación generó GMF (4x1000)</label>
          </div>
          <small>Pendiente en el backend: <code>POST /movimientos/normales</code> todavía no recibe GMF.</small>
        </div>
        <p class="error-form" id="mov-error" role="alert"></p>
      </div>

      <div class="pie-form">
        <small>Si no tienes conexión, se guarda en el celular y se envía después.</small>
        <button class="btn btn-primario" type="submit">Guardar movimiento</button>
      </div>
    </form>`;

  const form = c.querySelector('#form-mov');
  const monto = c.querySelector('#mov-monto');
  const error = c.querySelector('#mov-error');
  const selectCuenta = c.querySelector('#mov-cuenta');
  const categorias = await obtenerCategorias();

  // Monto con separador de miles mientras se escribe: 85000 → $ 85.000
  monto.addEventListener('input', () => {
    const digitos = monto.value.replace(/\D/g, '').slice(0, 13);
    monto.value = digitos ? cop(digitos) : '';
  });

  function pintarTipo() {
    c.querySelectorAll('.segmento button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.tipo === estado.tipo)));
    c.querySelector('#banda-mov').classList.toggle('banda-oscura', estado.tipo === 'INGRESO');
    c.querySelector('#gmf').hidden = estado.tipo !== 'GASTO';
    const lista = categorias.filter((x) => x.tipo_categoria === estado.tipo);
    if (!lista.some((x) => x.id_categoria === estado.categoria)) estado.categoria = lista[0]?.id_categoria ?? null;
    c.querySelector('#chips').innerHTML = lista.map((x) => `
      <button type="button" class="chip" data-id="${x.id_categoria}" aria-pressed="${x.id_categoria === estado.categoria}">${esc(x.nombre_categoria)}</button>`).join('');
  }

  c.querySelector('.segmento').addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-tipo]');
    if (!b) return;
    estado.tipo = b.dataset.tipo;
    pintarTipo();
  });
  c.querySelector('#chips').addEventListener('click', (ev) => {
    const b = ev.target.closest('.chip');
    if (!b) return;
    estado.categoria = Number(b.dataset.id);
    pintarTipo();
  });
  pintarTipo();

  // Cuentas activas del usuario (o las últimas guardadas si no hay red).
  try {
    let datos;
    try { datos = await obtenerMisCuentas(); } catch (e) {
      if (!(e instanceof ErrorDeRed) || !leerCache('cuentas')) throw e;
      datos = leerCache('cuentas').datos;
    }
    const activas = datos.cuentas.filter((x) => x.estado === 'ACTIVA');
    selectCuenta.innerHTML = activas.length
      ? activas.map((x) => `<option value="${x.id_cuenta}">${esc(x.nombre_cuenta)} · ${cop(x.saldo_actual)}</option>`).join('')
      : '<option value="">No tienes cuentas activas</option>';
  } catch (e) {
    selectCuenta.innerHTML = '<option value="">No se pudieron cargar las cuentas</option>';
    error.textContent = e.message;
  }

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    error.textContent = '';
    const valor = Number(monto.value.replace(/\D/g, ''));
    if (!valor) { error.textContent = 'Escribe un monto mayor a cero.'; monto.focus(); return; }
    if (!selectCuenta.value) { error.textContent = 'Elige una cuenta.'; return; }
    if (!estado.categoria) { error.textContent = 'Elige una categoría.'; return; }
    const fecha = form.fecha.value;
    if (!fecha || fecha > hoyISO()) { error.textContent = 'La fecha no puede ser futura.'; return; }

    const movimiento = {
      uuid_local: nuevoUUID(),
      id_cuenta: Number(selectCuenta.value),
      id_categoria: estado.categoria,
      tipo: estado.tipo,
      monto: valor,
      fecha_movimiento: fecha,
      descripcion: form.descripcion.value.trim() || null,
    };

    const boton = form.querySelector('button[type="submit"]');
    boton.disabled = true;
    boton.textContent = 'Guardando…';

    const guardarSinConexion = async () => {
      try {
        await guardarOffline('MOVIMIENTO_NORMAL', movimiento.uuid_local, movimiento);
      } catch (e) {
        error.textContent = e.message;
        boton.disabled = false;
        boton.textContent = 'Guardar movimiento';
        return;
      }
      aviso('Sin conexión: guardado en el celular. Se enviará al volver la conexión.', 'alerta');
      location.hash = '#/inicio';
    };

    if (!navigator.onLine) { await guardarSinConexion(); return; }
    try {
      const r = await crearMovimientoNormal(movimiento);
      aviso(r.mensaje || 'Movimiento registrado', 'ok');
      location.hash = '#/inicio';
    } catch (e) {
      if (e instanceof ErrorDeRed) { await guardarSinConexion(); return; }
      error.textContent = e.message;
      boton.disabled = false;
      boton.textContent = 'Guardar movimiento';
    }
  });
}
