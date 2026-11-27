
import {
  obtenerMisCuentas,
  obtenerCategorias,
  ErrorDeRed
} from '../api.js';

import {
  guardarOffline,
  sincronizar,
  operacionesLocales
} from '../offline.js';

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


const TASA_GMF = 0.004;

const copDecimales = valor =>
  new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(valor);


export async function render(c) {
  const estado = {
    tipo: 'GASTO',
    categoria: null
  };

  let uuidIntento = null;
  let datosIntento = null;
  let cuentas = [];
  let consulta = null;
  let cuentasDesdeCache = false;

  const usuarioInicial = Number(
    obtenerUsuario()?.id_usuario
  );

  const mismaSesion = () =>
    usuarioInicial > 0 &&
    Number(obtenerUsuario()?.id_usuario) === usuarioInicial;

  c.innerHTML = `
    <style>
      .mov-saldos {
        background: var(--c-bg-eef5f1);
        border-radius: 14px;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        font-size: 13px;
      }

      .mov-saldos .fila {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
      }

      .mov-saldos .fila strong {
        text-align: right;
      }

      .mov-saldos .principal {
        font-size: 15px;
        font-weight: 800;
        color: var(--c-tx-075640);
      }

      .mov-saldos .advertencia {
        font-size: 12px;
        color: var(--c-tx-975212);
        font-weight: 700;
        line-height: 1.5;
      }

      .mov-saldos .nota-saldo {
        font-size: 11px;
        color: var(--c-tx-59675f);
        line-height: 1.45;
      }

      .mov-gmf-nota {
        font-size: 12px;
        color: var(--c-tx-705821);
        line-height: 1.5;
      }
    </style>

    <form id="form-mov" novalidate>
      <header class="banda banda-form" id="banda-mov">
        <div class="banda-fila">
          <a
            class="btn-icono"
            href="#/inicio"
            aria-label="Volver al inicio"
          >
            ${icono('atras')}
          </a>

          <h1 class="banda-titulo">
            Nuevo movimiento
          </h1>
        </div>

        <div
          class="segmento"
          role="group"
          aria-label="Tipo de movimiento"
        >
          <button
            type="button"
            data-tipo="GASTO"
            aria-pressed="true"
          >
            Gasto
          </button>

          <button
            type="button"
            data-tipo="INGRESO"
            aria-pressed="false"
          >
            Ingreso
          </button>
        </div>

        <div class="monto-grande">
          <label for="mov-monto">
            ¿Cuánto fue? (COP)
          </label>

          <input
            id="mov-monto"
            name="monto"
            inputmode="numeric"
            autocomplete="off"
            placeholder="$ 0"
            required
          >
        </div>
      </header>

      <div class="cuerpo-form">
        <div class="campo">
          <label for="mov-cuenta">
            Cuenta
          </label>

          <select
            id="mov-cuenta"
            name="cuenta"
            required
          >
            <option value="">
              Cargando cuentas…
            </option>
          </select>

          <div
            class="mov-saldos"
            id="mov-saldos"
            aria-live="polite"
          >
            Consultando saldos…
          </div>
        </div>

        <div class="campo">
          <label for="mov-fecha">
            Fecha
          </label>

          <input
            id="mov-fecha"
            name="fecha"
            type="date"
            max="${hoyISO()}"
            value="${hoyISO()}"
            required
          >
        </div>

        <div class="campo">
          <label for="mov-desc">
            Descripción
            <span class="opcional">
              opcional
            </span>
          </label>

          <input
            id="mov-desc"
            name="descripcion"
            maxlength="255"
            placeholder="Ej. almuerzo con el equipo"
          >
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
            <input
              id="mov-gmf"
              name="aplica_gmf"
              type="checkbox"
            >

            <label for="mov-gmf">
              Este gasto generó GMF (4×1000)
            </label>
          </div>

          <small class="mov-gmf-nota">
            Márcalo solo si corresponde el cobro.
            El 0,4 % se sumará al dinero que sale
            de la cuenta.
          </small>
        </div>

        <p
          class="error-form"
          id="mov-error"
          role="alert"
        ></p>
      </div>

      <div class="pie-form">
        <small>
          Si no tienes conexión, se guarda
          en el celular y se envía después.
        </small>

        <button
          class="btn btn-primario"
          type="submit"
        >
          Guardar movimiento
        </button>
      </div>
    </form>
  `;

  const form = c.querySelector('#form-mov');
  const monto = c.querySelector('#mov-monto');
  const error = c.querySelector('#mov-error');
  const selectCuenta = c.querySelector('#mov-cuenta');
  const gmf = c.querySelector('#mov-gmf');

  let categorias = [];

  const avisoCategorias = c.querySelector(
    '#aviso-categorias'
  );

  const importeActual = () => Number(
    monto.value.replace(/\D/g, '')
  ) || 0;

  const gmfActual = () => {
    if (estado.tipo !== 'GASTO' || !gmf.checked) {
      return 0;
    }

    // Mismo redondeo a centavos que el backend.
    return Math.round(
      importeActual() * TASA_GMF * 100
    ) / 100;
  };


  // ------------------------------------
  // CARGAR CATEGORÍAS
  // ------------------------------------

  try {
    const respuesta = await obtenerCategorias();

    if (!Array.isArray(respuesta)) {
      throw new Error(
        'El servidor devolvió un formato ' +
        'de categorías inválido.'
      );
    }

    if (!mismaSesion()) return;

    categorias = respuesta.filter(cat =>
      cat.estado === 'ACTIVA' &&
      ['GASTO', 'INGRESO'].includes(
        cat.tipo_categoria
      ) &&
      Number.isSafeInteger(
        Number(cat.id_categoria)
      ) &&
      Number(cat.id_categoria) > 0
    );

    guardarCache('categorias', categorias);
    avisoCategorias.textContent = '';

  } catch (e) {
    if (e instanceof ErrorDeRed) {
      const cache = leerCache('categorias');

      if (Array.isArray(cache?.datos)) {
        categorias = cache.datos.filter(cat =>
          cat.estado === 'ACTIVA' &&
          ['GASTO', 'INGRESO'].includes(
            cat.tipo_categoria
          )
        );

        avisoCategorias.textContent =
          'Sin conexión: estás utilizando las ' +
          'últimas categorías guardadas. ' +
          'Algunas podrían haber cambiado ' +
          'en el servidor.';

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


  // ------------------------------------
  // MONTO, TIPO Y GMF
  // ------------------------------------

  monto.addEventListener('input', () => {
    const digitos = monto.value
      .replace(/\D/g, '')
      .slice(0, 13);

    monto.value = digitos
      ? cop(digitos)
      : '';

    pintarSaldos();
  });

  gmf.addEventListener('change', pintarSaldos);


  function pintarTipo() {
    c.querySelectorAll('.segmento button')
      .forEach(b => {
        b.setAttribute(
          'aria-pressed',
          String(b.dataset.tipo === estado.tipo)
        );
      });

    c.querySelector('#banda-mov')
      .classList.toggle(
        'banda-oscura',
        estado.tipo === 'INGRESO'
      );

    const esGasto = estado.tipo === 'GASTO';

    c.querySelector('#gmf').hidden = !esGasto;

    // Nunca enviar GMF en un ingreso.
    if (!esGasto) {
      gmf.checked = false;
    }

    gmf.disabled = !esGasto;

    pintarOpcionesCuenta();
    pintarSaldos();

    const lista = categorias.filter(cat =>
      cat.tipo_categoria === estado.tipo &&
      cat.estado === 'ACTIVA' &&
      Number.isSafeInteger(
        Number(cat.id_categoria)
      ) &&
      Number(cat.id_categoria) > 0
    );

    if (!lista.some(cat =>
      Number(cat.id_categoria) ===
      Number(estado.categoria)
    )) {
      estado.categoria = lista.length
        ? Number(lista[0].id_categoria)
        : null;
    }

    const chips = c.querySelector('#chips');

    if (!lista.length) {
      chips.innerHTML = `
        <p class="vacio">
          No hay categorías disponibles para
          ${
            estado.tipo === 'GASTO'
              ? 'gastos'
              : 'ingresos'
          }.
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
            aria-pressed="${
              id === estado.categoria
            }"
          >
            ${esc(cat.nombre_categoria)}
          </button>
        `;
      }).join('');
    }
  }


  c.querySelector('.segmento')
    .addEventListener('click', ev => {
      const b = ev.target.closest(
        'button[data-tipo]'
      );

      if (!b) return;

      estado.tipo = b.dataset.tipo;
      pintarTipo();
    });


  c.querySelector('#chips')
    .addEventListener('click', ev => {
      const b = ev.target.closest('.chip');

      if (!b) return;

      estado.categoria = Number(b.dataset.id);
      pintarTipo();
    });

  pintarTipo();


  // ------------------------------------
  // SELECTOR DE CUENTAS
  // ------------------------------------

  function pintarOpcionesCuenta() {
    const anterior = selectCuenta.value;

    const activas = cuentas.filter(
      cu => cu.estado === 'ACTIVA'
    );

    selectCuenta.innerHTML = activas.length
      ? activas.map(cu => {
        const r = encontrarSaldoReserva(
          consulta,
          cu.id_cuenta
        );

        const texto = estado.tipo === 'INGRESO'
          ? `Saldo real ${cop(cu.saldo_actual)}`
          : r
            ? (
                `Libre ${
                  cop(
                    Number(cu.saldo_actual) -
                    Number(r.monto_reservado)
                  )
                }`
              )
            : 'Saldo libre por verificar';

        return `
          <option value="${
            Number(cu.id_cuenta)
          }">
            ${esc(cu.nombre_cuenta)} ·
            ${esc(texto)}
          </option>
        `;
      }).join('')
      : `
        <option value="">
          No tienes cuentas activas
        </option>
      `;

    if (activas.some(
      cu => String(cu.id_cuenta) === anterior
    )) {
      selectCuenta.value = anterior;
    }
  }


  function pintarSaldos() {
    const caja = c.querySelector('#mov-saldos');

    if (!caja) return;

    const cuenta = cuentas.find(
      cu =>
        String(cu.id_cuenta) ===
        selectCuenta.value
    );

    if (!cuenta) {
      caja.textContent =
        'Selecciona una cuenta para consultar su saldo.';
      return;
    }

    const real = Number(cuenta.saldo_actual);

    const r = encontrarSaldoReserva(
      consulta,
      cuenta.id_cuenta
    );

    const reservado = r
      ? Number(r.monto_reservado)
      : null;

    const libre = reservado === null
      ? null
      : real - reservado;

    const importe = importeActual();
    const impuesto = gmfActual();
    const debito = importe + impuesto;

    const avisoFuente = cuentasDesdeCache
      ? 'Cuentas guardadas · confirmar al sincronizar. '
      : '';

    const avisoReserva = textoEstadoSaldo(consulta);

    if (estado.tipo === 'INGRESO') {
      caja.innerHTML = `
        <div class="fila">
          <span>Saldo real actual</span>
          <strong class="monto">
            ${cop(real)}
          </strong>
        </div>

        <div class="fila principal">
          <span>Estimado después del ingreso</span>
          <strong class="monto">
            ${cop(real + importe)}
          </strong>
        </div>

        <div class="nota-saldo">
          ${esc(avisoFuente)}
          Estimación: no incluye operaciones pendientes.
          ${esc(avisoReserva)}
        </div>
      `;

      return;
    }

    const supera =
      libre !== null &&
      debito > libre;

    caja.innerHTML = `
      <div class="fila">
        <span>Saldo real</span>
        <strong class="monto">
          ${cop(real)}
        </strong>
      </div>

      <div class="fila">
        <span>Reservado en metas</span>
        <strong class="monto">
          ${
            reservado === null
              ? 'Sin verificar'
              : cop(reservado)
          }
        </strong>
      </div>

      <div class="fila principal">
        <span>Disponible para gastar</span>
        <strong class="monto">
          ${
            libre === null
              ? 'Sin verificar'
              : cop(libre)
          }
        </strong>
      </div>

      <div class="fila">
        <span>GMF estimado (4×1000)</span>
        <strong class="monto">
          ${copDecimales(impuesto)}
        </strong>
      </div>

      <div class="fila">
        <span>Total a descontar (gasto + GMF)</span>
        <strong class="monto">
          ${copDecimales(debito)}
        </strong>
      </div>

      <div class="fila principal">
        <span>Libre después (estimado)</span>
        <strong class="monto">
          ${
            libre === null
              ? 'Sin verificar'
              : copDecimales(libre - debito)
          }
        </strong>
      </div>

      ${
        supera
          ? `
            <div class="advertencia">
              El gasto y el GMF superan el saldo libre
              mostrado. Reduce el monto o libera ahorro
              desde Metas.
            </div>
          `
          : ''
      }

      <div class="nota-saldo">
        ${esc(avisoFuente + avisoReserva)}
        La validación final se realizará en el servidor.
      </div>
    `;
  }


  selectCuenta.addEventListener(
    'change',
    pintarSaldos
  );


  // ------------------------------------
  // CARGAR CUENTAS Y RESERVAS
  // ------------------------------------

  try {
    let datos;

    try {
      datos = await obtenerMisCuentas();

      if (!mismaSesion()) return;

      guardarCache('cuentas', datos);

    } catch (e) {
      const cache = leerCache('cuentas');

      if (
        !(e instanceof ErrorDeRed) ||
        !Array.isArray(cache?.datos?.cuentas)
      ) {
        throw e;
      }

      datos = cache.datos;
      cuentasDesdeCache = true;
    }

    cuentas = datos.cuentas.filter(
      cu => cu.estado === 'ACTIVA'
    );

    try {
      consulta = await consultarReservasVisibles();

    } catch (e) {
      console.warn(
        'Saldo libre no disponible:',
        e
      );
    }

    if (!mismaSesion()) return;

    pintarOpcionesCuenta();
    pintarSaldos();

  } catch (e) {
    selectCuenta.innerHTML = `
      <option value="">
        No se pudieron cargar las cuentas
      </option>
    `;

    error.textContent = e.message;
    pintarSaldos();
  }


  // ------------------------------------
  // GUARDAR MOVIMIENTO (LOCAL-FIRST)
  // ------------------------------------

  form.addEventListener('submit', async ev => {
    ev.preventDefault();

    const boton = form.querySelector(
      'button[type="submit"]'
    );

    if (boton.disabled) return;

    error.textContent = '';

    const valor = importeActual();

    if (!valor) {
      error.textContent =
        'Escribe un monto mayor a cero.';

      monto.focus();
      return;
    }

    if (!selectCuenta.value) {
      error.textContent =
        'Elige una cuenta.';
      return;
    }

    if (!estado.categoria) {
      error.textContent =
        'Elige una categoría.';
      return;
    }

    const fecha = form.fecha.value;

    if (!fecha || fecha > hoyISO()) {
      error.textContent =
        'La fecha no puede ser futura.';
      return;
    }

    const datosActuales = {
      id_cuenta: Number(selectCuenta.value),
      id_categoria: estado.categoria,
      tipo: estado.tipo,
      monto: valor,
      fecha_movimiento: fecha,
      descripcion:
        form.descripcion.value.trim() || null,
      aplica_gmf:
        estado.tipo === 'GASTO' && gmf.checked
    };

    const contenidoActual = JSON.stringify(
      datosActuales
    );

    if (
      uuidIntento !== null &&
      contenidoActual !== datosIntento
    ) {
      error.textContent =
        'Existe un intento anterior sin confirmar. ' +
        'Consulta tus movimientos pendientes antes ' +
        'de modificarlo o registrar otro.';

      return;
    }

    if (uuidIntento === null) {
      uuidIntento = nuevoUUID();
      datosIntento = contenidoActual;
    }

    const movimiento = {
      uuid_local: uuidIntento,
      ...datosActuales
    };

    boton.disabled = true;
    boton.textContent = 'Guardando…';


    const guardarSinConexion = async () => {
      try {
        await guardarOffline(
          'MOVIMIENTO_NORMAL',
          movimiento.uuid_local,
          movimiento
        );

      } catch (e) {
        error.textContent = e.message;
        boton.disabled = false;
        boton.textContent =
          'Guardar movimiento';

        return;
      }

      aviso(
        'Sin conexión: guardado en el celular. ' +
        'Se enviará al volver la conexión.',
        'alerta'
      );

      location.hash = '#/inicio';
    };

    if (!navigator.onLine) {
      await guardarSinConexion();
      return;
    }


    // PASO 1: guardar en IndexedDB.

    try {
      await guardarOffline(
        'MOVIMIENTO_NORMAL',
        movimiento.uuid_local,
        movimiento
      );

    } catch (e) {
      error.textContent =
        'No se pudo guardar el movimiento ' +
        'en el dispositivo: ' +
        e.message;

      boton.disabled = false;
      boton.textContent = 'Guardar movimiento';
      return;
    }


    // PASO 2: sincronización.

    if (navigator.onLine) {
      try {
        await sincronizar();

      } catch (e) {
        console.warn(
          'La sincronización no pudo completarse:',
          e
        );
      }
    }


    // PASO 3: consultar el estado local.

    let operacionLocal;
    let consultaCorrecta = false;

    try {
      const locales = await operacionesLocales();

      if (!Array.isArray(locales)) {
        throw new Error(
          'La cola local devolvió datos inválidos.'
        );
      }

      operacionLocal = locales.find(
        op =>
          op.uuid_operacion ===
          movimiento.uuid_local
      );

      consultaCorrecta = true;

    } catch (e) {
      console.warn(
        'No se pudo consultar el estado local:',
        e
      );
    }


    // PASO 4: informar el resultado.

    if (!consultaCorrecta) {
      aviso(
        'Movimiento guardado. Revisa su estado ' +
        'en Movimientos antes de repetirlo.',
        'alerta'
      );

    } else if (
      operacionLocal?.estado_sync === 'ERROR'
    ) {
      aviso(
        'El servidor rechazó el movimiento. ' +
        'Revísalo en Movimientos.',
        'alerta'
      );

    } else if (operacionLocal) {
      aviso(
        'Movimiento guardado en el dispositivo. ' +
        'Se enviará cuando pueda sincronizarse.',
        'alerta'
      );

    } else {
      aviso(
        'Movimiento sincronizado correctamente.',
        'ok'
      );
    }

    location.hash = '#/inicio';
  });
}
