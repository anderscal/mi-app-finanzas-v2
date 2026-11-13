import { obtenerMisCuentas, obtenerCategorias, crearMovimientoNormal, ErrorDeRed } from '../api.js';
import { guardarOffline } from '../offline.js';
import {
  cop,
  esc,
  icono,
  hoyISO,
  nuevoUUID,
  aviso,
  leerCache,
  guardarCache
} from '../util.js';

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
        <div class="campo">
          <label for="mov-desc">Descripción <span class="opcional">opcional</span></label>
          <input id="mov-desc" name="descripcion" maxlength="255" placeholder="Ej. almuerzo con el equipo">
        </div>
        
<fieldset class="campo">
  <legend>Categoría</legend>

  <div class="chips" id="chips"></div>

  <p
    id="aviso-categorias"
    class="nota"
    aria-live="polite"
  ></p>
</fieldset>

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

  let categorias = [];

  const avisoCategorias = c.querySelector(
    '#aviso-categorias'
  );

  try {
    // Primero intentamos obtener las categorías
    // actualizadas desde PostgreSQL.
    const respuesta = await obtenerCategorias();

    if (!Array.isArray(respuesta)) {
      throw new Error(
        'El servidor devolvió un formato de categorías inválido.'
      );
    }

    categorias = respuesta.filter(cat =>
      cat.estado === 'ACTIVA' &&
      ['GASTO', 'INGRESO'].includes(cat.tipo_categoria) &&
      Number.isSafeInteger(Number(cat.id_categoria)) &&
      Number(cat.id_categoria) > 0
    );

    // La caché ya está separada por usuario
    // desde el paso 21.2.
    guardarCache('categorias', categorias);

    avisoCategorias.textContent = '';

  } catch (e) {

    // Solo utilizamos caché cuando existe un
    // problema de conexión, no ante errores
    // de autorización o validación del servidor.
    if (e instanceof ErrorDeRed) {

      const cache = leerCache('categorias');

      if (Array.isArray(cache?.datos)) {

        categorias = cache.datos.filter(cat =>
          cat.estado === 'ACTIVA' &&
          ['GASTO', 'INGRESO'].includes(cat.tipo_categoria)
        );

        avisoCategorias.textContent =
          'Sin conexión: estás utilizando las últimas ' +
          'categorías guardadas. Algunas podrían haber ' +
          'cambiado en el servidor.';

      } else {

        avisoCategorias.textContent =
          'No hay conexión ni categorías guardadas. ' +
          'Conéctate para descargarlas.';

      }

    } else {

      avisoCategorias.textContent =
        'No fue posible consultar las categorías: ' +
        e.message;

    }
  }


  // Monto con separador de miles mientras se escribe: 85000 → $ 85.000
  monto.addEventListener('input', () => {
    const digitos = monto.value.replace(/\D/g, '').slice(0, 13);
    monto.value = digitos ? cop(digitos) : '';
  });

  function pintarTipo() {
    c.querySelectorAll('.segmento button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.tipo === estado.tipo)));
    c.querySelector('#banda-mov').classList.toggle('banda-oscura', estado.tipo === 'INGRESO');
    c.querySelector('#gmf').hidden = estado.tipo !== 'GASTO';

    const lista = categorias.filter(cat =>
      cat.tipo_categoria === estado.tipo &&
      cat.estado === 'ACTIVA' &&
      Number.isSafeInteger(Number(cat.id_categoria)) &&
      Number(cat.id_categoria) > 0
    );

    // Mantener la categoría seleccionada si todavía
    // existe en la lista del tipo actual.
    if (!lista.some(cat =>
      Number(cat.id_categoria) === Number(estado.categoria)
    )) {
      estado.categoria = lista.length
        ? Number(lista[0].id_categoria)
        : null;
    }

    const chips = c.querySelector('#chips');

    if (lista.length === 0) {

      chips.innerHTML = `
    <p class="vacio">
      No hay categorías disponibles para
      ${estado.tipo === 'GASTO' ? 'gastos' : 'ingresos'}.
    </p>
  `;

    } else {

      chips.innerHTML = lista.map(cat => {

        const id = Number(cat.id_categoria);

        return `
      <button
        type="button"
        class="chip"
        data-id="${id}"
        aria-pressed="${id === estado.categoria}"
      >
        ${esc(cat.nombre_categoria)}
      </button>
    `;

      }).join('');

    }
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
