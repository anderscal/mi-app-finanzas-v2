
import {
  obtenerMisCuentas,
  obtenerPlanificacion,
  ErrorDeRed
} from '../api.js';

import {
  guardarOffline,
  sincronizar
} from '../offline.js';

import {
  obtenerOperacionesLocales
} from '../offline-db.js';

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

import {
  consultarReservasVisibles,
  encontrarSaldoReserva,
  textoEstadoSaldo
} from '../saldo-consulta.js';

import { obtenerUsuario } from '../sesion.js';


// Pantalla de pago (POR_PAGAR)
// o cobro de préstamo (POR_COBRAR).
// Ruta: #/abonar/<id_obligacion>

export async function render(c, idObligacion) {

  const idUsuario = Number(obtenerUsuario()?.id_usuario);
  const mismaSesion = () =>
    Number.isSafeInteger(idUsuario) &&
    idUsuario > 0 &&
    Number(obtenerUsuario()?.id_usuario) === idUsuario;

  if (!mismaSesion()) return;

  const uuidLocal = nuevoUUID();
  const id = Number(idObligacion);

  if (!Number.isSafeInteger(id) || id <= 0) {
    c.innerHTML = `
      <section class="seccion">
        <p class="error-general">
          Identificador de obligación no válido.
        </p>
        <a href="#/deudas">Volver</a>
      </section>
    `;
    return;
  }

  let obligacion = null;

  try {

    const plan = await obtenerPlanificacion();

    if (!mismaSesion()) return;

    guardarCache('planificacion', plan);

    obligacion = plan.obligaciones.find(
      o => o.id_obligacion === id
    ) || null;

  } catch (e) {

    // Solo recuperar planificación desde caché
    // cuando el problema es la conexión.
    if (e instanceof ErrorDeRed) {

      const cache = leerCache('planificacion');

      obligacion = cache?.datos?.obligaciones?.find(
        o => o.id_obligacion === id
      ) || null;

    } else {

      c.innerHTML = `
        <section class="seccion">
          <p class="error-general">
            ${esc(e.message)}
          </p>
        </section>
      `;

      return;
    }
  }

  if (!mismaSesion()) return;

  if (!obligacion) {

    c.innerHTML = `
      <section class="seccion">
        <p class="vacio">
          No se encontró la obligación.
          Conéctate para actualizar tus datos.
        </p>
        <a href="#/deudas">Volver a Deudas</a>
      </section>
    `;

    return;
  }

  if (obligacion.estado !== 'ACTIVA') {

    c.innerHTML = `
      <header class="banda">
        <div class="banda-fila">
          <a
            class="btn-icono"
            href="#/deudas"
            aria-label="Volver"
          >
            ${icono('atras')}
          </a>

          <h1 class="banda-titulo">
            ${esc(obligacion.nombre_obligacion)}
          </h1>
        </div>
      </header>

      <section class="seccion">
        <p class="vacio">
          Esta obligación está
          ${esc(obligacion.estado.toLowerCase())}.
          No admite más abonos.
        </p>
      </section>
    `;

    return;
  }

  const porPagar =
    obligacion.tipo_obligacion === 'POR_PAGAR';

  const verbo = porPagar ? 'pago' : 'cobro';

  const pendiente = Number(
    obligacion.monto_pendiente
  );

  c.innerHTML = `
    <form id="form-ab" novalidate>

      <header class="banda banda-form${
        porPagar ? '' : ' banda-oscura'
      }">

        <div class="banda-fila">

          <a
            class="btn-icono"
            href="#/deudas"
            aria-label="Volver a deudas"
          >
            ${icono('atras')}
          </a>

          <h1 class="banda-titulo">
            Registrar ${verbo}
          </h1>

        </div>

        <p class="banda-sub">
          ${esc(obligacion.nombre_obligacion)}
          ·
          ${porPagar ? 'debes' : 'te deben'}

          <span class="monto">
            ${cop(pendiente)}
          </span>
        </p>

        <div class="monto-grande">

          <label for="ab-monto">
            ${
              porPagar
                ? '¿Cuánto vas a pagar?'
                : '¿Cuánto te devolvieron?'
            } (COP)
          </label>

          <input
            id="ab-monto"
            name="monto"
            inputmode="numeric"
            autocomplete="off"
            placeholder="$ 0"
            required
          >

        </div>

        ${
          pendiente > 0
            ? `
              <button
                type="button"
                class="chip chip-banda"
                id="ab-todo"
              >
                ${
                  porPagar
                    ? 'Pagar todo'
                    : 'Cobrar todo'
                }
                · ${cop(pendiente)}
              </button>
            `
            : ''
        }

      </header>


      <div class="cuerpo-form">

        <div class="campo">

          <label for="ab-cuenta">
            ${porPagar ? 'Pagar desde' : 'Recibir en'}
          </label>

          <select
            id="ab-cuenta"
            name="cuenta"
            required
          >
            <option value="">Cargando…</option>
          </select>

          ${porPagar ? '<p class="nota" id="ab-saldo-estado"></p>' : ''}

        </div>


        <div class="campo">

          <label for="ab-fecha">Fecha</label>

          <input
            id="ab-fecha"
            name="fecha"
            type="date"
            max="${hoyISO()}"
            value="${hoyISO()}"
            required
          >

        </div>


        <div class="campo">

          <label for="ab-desc">
            Descripción
            <span class="opcional">opcional</span>
          </label>

          <input
            id="ab-desc"
            name="descripcion"
            maxlength="255"
            placeholder="${
              porPagar
                ? 'Ej. cuota de noviembre'
                : 'Ej. abono en efectivo'
            }"
          >

        </div>


        <div
          class="resumen-abono"
          id="ab-resumen"
          ${pendiente > 0 ? '' : 'hidden'}
        >

          <div>
            <span>Pendiente ahora</span>

            <strong class="monto">
              ${cop(pendiente)}
            </strong>
          </div>

          <div>
            <span>Este ${verbo}</span>

            <strong
              class="monto ${
                porPagar ? 'gasto' : 'ingreso'
              }"
              id="ab-v-monto"
            >
              $ 0
            </strong>
          </div>

          <div class="total-abono">

            <span>Quedará pendiente</span>

            <strong
              class="monto"
              id="ab-v-queda"
            >
              ${cop(pendiente)}
            </strong>

          </div>

        </div>


        <p class="nota">

          ${
            porPagar
              ? 'El pago sale de tu cuenta, pero no cuenta como gasto ordinario en tu resumen.'
              : 'El cobro entra a tu cuenta, pero no cuenta como ingreso ordinario en tu resumen.'
          }

          Si el pendiente llega a cero,
          la obligación queda saldada.

        </p>

        <p
          class="error-form"
          id="ab-error"
          role="alert"
        ></p>

      </div>


      <div class="pie-form">

        <small>
          El abono se guarda primero en este
          dispositivo y luego se sincroniza.
        </small>

        <button
          class="btn btn-primario"
          type="submit"
        >
          Registrar ${verbo}
        </button>

      </div>

    </form>
  `;


  // -------------------------------------
  // ELEMENTOS DEL FORMULARIO
  // -------------------------------------

  const form = c.querySelector('#form-ab');
  const monto = c.querySelector('#ab-monto');
  const cuenta = c.querySelector('#ab-cuenta');
  const error = c.querySelector('#ab-error');

  const valor = () =>
    Number(monto.value.replace(/\D/g, ''));


  // -------------------------------------
  // ACTUALIZAR RESUMEN VISUAL
  // -------------------------------------

  function recalcular() {

    if (pendiente <= 0) return;

    const m = valor();

    c.querySelector('#ab-v-monto').textContent =
      (porPagar ? '− ' : '+ ') + cop(m);

    const queda = pendiente - m;

    const elemento = c.querySelector(
      '#ab-v-queda'
    );

    elemento.textContent =
      queda === 0
        ? '$ 0 · saldada'
        : cop(queda);

    elemento.classList.toggle(
      'gasto',
      queda < 0
    );
  }


  monto.addEventListener('input', () => {

    const digitos = monto.value
      .replace(/\D/g, '')
      .slice(0, 13);

    monto.value = digitos
      ? cop(digitos)
      : '';

    recalcular();
  });


  c.querySelector('#ab-todo')?.addEventListener(
    'click',
    () => {

      monto.value = cop(pendiente);

      recalcular();
    }
  );


  // -------------------------------------
  // CARGAR CUENTAS FINANCIERAS
  // -------------------------------------

  try {

    let datos;

    try {

      datos = await obtenerMisCuentas();

      if (!mismaSesion()) return;

      guardarCache('cuentas', datos);

    } catch (e) {

      if (!(e instanceof ErrorDeRed)) {
        throw e;
      }

      const cache = leerCache('cuentas');

      if (!cache?.datos) {
        throw e;
      }

      datos = cache.datos;
    }

    const activas = datos.cuentas.filter(
      x => x.estado === 'ACTIVA'
    );

    let consulta = null;

    if (porPagar) {
      try {
        consulta = await consultarReservasVisibles();
      } catch (e) {
        // Sin reservas verificables, no mostrar saldo real como libre.
      }
    }

    if (!mismaSesion()) return;

    const estadoSaldo = c.querySelector('#ab-saldo-estado');
    if (estadoSaldo) {
      estadoSaldo.textContent = textoEstadoSaldo(consulta);
    }

    cuenta.innerHTML = activas.length
      ? activas.map(x => {
        const r = encontrarSaldoReserva(consulta, x.id_cuenta);
        const libre = r?.saldo_libre;
        const texto = !porPagar
          ? `Saldo real ${cop(x.saldo_actual)}`
          : libre != null && Number.isFinite(Number(libre))
            ? `Libre ${cop(libre)}`
            : 'Saldo libre por verificar';

        return `
          <option value="${Number(x.id_cuenta)}">
            ${esc(x.nombre_cuenta)}
            · ${esc(texto)}
          </option>
        `;
      }).join('')
      : '<option value="">No tienes cuentas activas</option>';

  } catch (e) {

    cuenta.innerHTML =
      '<option value="">Sin cuentas</option>';

    error.textContent = e.message;
  }


  // -------------------------------------
  // GUARDAR ABONO Y SINCRONIZAR
  // -------------------------------------

  form.addEventListener('submit', async ev => {

    ev.preventDefault();

    if (!mismaSesion()) return;

    const boton = form.querySelector(
      'button[type="submit"]'
    );

    if (boton.disabled) return;

    error.textContent = '';

    const m = valor();

    if (!Number.isSafeInteger(m) || m <= 0) {
      error.textContent =
        'Escribe un monto válido mayor a cero.';
      monto.focus();
      return;
    }

    if (m > pendiente) {
      error.textContent =
        `El ${verbo} no puede superar lo pendiente ` +
        `(${cop(pendiente)}).`;
      return;
    }

    if (!cuenta.value) {
      error.textContent = 'Elige una cuenta.';
      return;
    }

    if (!form.fecha.value || form.fecha.value > hoyISO()) {
      error.textContent =
        'La fecha no puede ser futura.';
      return;
    }

    const datos = {
      uuid_local: uuidLocal,
      id_cuenta: Number(cuenta.value),
      id_obligacion: id,
      monto: m,
      fecha_movimiento: form.fecha.value,
      descripcion:
        form.descripcion.value.trim() || null
    };


    // -----------------------------------
    // 1. GUARDAR PRIMERO EN INDEXEDDB
    // -----------------------------------

    boton.disabled = true;
    boton.textContent = `Guardando ${verbo}…`;

    try {

      await guardarOffline(
        'ABONO_OBLIGACION',
        uuidLocal,
        datos
      );

    } catch (e) {

      error.textContent =
        'No se pudo guardar el abono: ' +
        e.message;

      boton.disabled = false;
      boton.textContent = `Registrar ${verbo}`;

      return;
    }


    // -----------------------------------
    // 2. SINCRONIZAR SI EXISTE CONEXION
    // -----------------------------------

    if (navigator.onLine) {

      boton.textContent = 'Sincronizando…';

      try {

        await sincronizar();

      } catch (e) {

        console.warn(
          'No se pudo completar la sincronización:',
          e
        );
      }
    }


    // -----------------------------------
    // 3. CONSULTAR EL ESTADO LOCAL
    // -----------------------------------

    let operacionLocal = null;
    let lecturaCorrecta = false;

    try {

      const operaciones =
        await obtenerOperacionesLocales();

      if (!Array.isArray(operaciones)) {
        throw new Error(
          'La cola local devolvió datos inválidos.'
        );
      }

      operacionLocal = operaciones.find(
        op => op.uuid_operacion === uuidLocal
      ) || null;

      lecturaCorrecta = true;

    } catch (e) {

      console.warn(
        'No se pudo consultar el abono local:',
        e
      );
    }


    // -----------------------------------
    // 4. INFORMAR EL RESULTADO
    // -----------------------------------

    if (!lecturaCorrecta) {

      aviso(
        'Abono guardado. No se pudo comprobar ' +
        'su estado actual. Revísalo en ' +
        'Movimientos antes de repetirlo.',
        'alerta'
      );

    } else if (
      operacionLocal?.estado_sync === 'ERROR'
    ) {

      aviso(
        'El servidor rechazó el abono. ' +
        'Revísalo en Movimientos.',
        'alerta'
      );

    } else if (operacionLocal) {

      aviso(
        'Abono guardado en el dispositivo. ' +
        'Está pendiente de sincronización.',
        'alerta'
      );

    } else {

      aviso(
        'El abono ya no está pendiente. ' +
        'Comprueba el resultado en Deudas ' +
        'y préstamos.',
        'ok'
      );
    }

    location.hash = '#/deudas';

  });
}
