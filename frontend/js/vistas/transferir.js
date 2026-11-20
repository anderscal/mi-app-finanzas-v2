
import {
  obtenerMisCuentas,
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


const TASA_GMF = 0.004;

const monedaExacta = valor =>
  new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(valor);


export async function render(c) {
  const uuidOperacion = nuevoUUID();

  let cuentas = [];
  let consulta = null;
  let cuentasDesdeCache = false;
  let datosIntento = null;

  const usuarioInicial = Number(
    obtenerUsuario()?.id_usuario
  );

  const mismaSesion = () =>
    usuarioInicial > 0 &&
    Number(obtenerUsuario()?.id_usuario) === usuarioInicial;

  c.innerHTML = `
    <style>
      .tr-saldos {
        background: #edf5f0;
        border-radius: 14px;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 7px;
      }

      .tr-saldos .fila {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        font-size: 13px;
      }

      .tr-saldos .principal {
        font-weight: 800;
        color: #075640;
        font-size: 14px;
      }

      .tr-saldos .aviso {
        font-size: 12px;
        font-weight: 700;
        color: #95521c;
        line-height: 1.45;
      }

      .tr-saldos .fuente {
        font-size: 11px;
        color: #5d6b62;
        line-height: 1.4;
      }
    </style>

    <form id="form-tr" novalidate>
      <header class="banda banda-form">
        <div class="banda-fila">
          <a
            class="btn-icono"
            href="#/inicio"
            aria-label="Volver al inicio"
          >
            ${icono('atras')}
          </a>

          <h1 class="banda-titulo">
            Pasar entre mis cuentas
          </h1>
        </div>

        <div class="monto-grande">
          <label for="tr-monto">
            Monto a transferir (COP)
          </label>

          <input
            id="tr-monto"
            name="monto"
            inputmode="numeric"
            autocomplete="off"
            placeholder="$ 0"
            required
          >
        </div>
      </header>

      <div class="cuerpo-form">
        <div class="par-cuentas">
          <div class="campo">
            <label for="tr-origen">
              Desde
            </label>

            <select
              id="tr-origen"
              name="origen"
              required
            >
              <option value="">
                Cargando…
              </option>
            </select>
          </div>

          <button
            type="button"
            class="btn-intercambiar"
            id="tr-cambiar"
            aria-label="Intercambiar origen y destino"
          >
            ${icono('transferir', 20)}
          </button>

          <div class="campo">
            <label for="tr-destino">
              Hacia
            </label>

            <select
              id="tr-destino"
              name="destino"
              required
            >
              <option value="">
                Cargando…
              </option>
            </select>
          </div>
        </div>

        <div
          class="tr-saldos"
          id="tr-saldos"
          aria-live="polite"
        >
          Consultando saldo libre…
        </div>

        <div class="campo">
          <label for="tr-fecha">
            Fecha
          </label>

          <input
            id="tr-fecha"
            name="fecha"
            type="date"
            max="${hoyISO()}"
            value="${hoyISO()}"
            required
          >
        </div>

        <div class="campo">
          <label for="tr-motivo">
            Motivo
            <span class="opcional">
              opcional
            </span>
          </label>

          <input
            id="tr-motivo"
            name="motivo"
            maxlength="150"
            placeholder="Movimiento interno"
          >
        </div>

        <div class="gmf">
          <div class="gmf-fila">
            <input
              id="tr-gmf"
              type="checkbox"
            >

            <label for="tr-gmf">
              Esta operación generó GMF (4x1000)
            </label>
          </div>

          <div class="gmf-detalle">
            <div>
              <span>GMF estimado</span>
              <strong
                class="monto"
                id="tr-v-gmf"
              >
                $ 0
              </strong>
            </div>

            <div>
              <span id="tr-t-sale">
                Sale de la cuenta origen
              </span>

              <strong
                class="monto gasto"
                id="tr-v-sale"
              >
                $ 0
              </strong>
            </div>

            <div>
              <span id="tr-t-entra">
                Entra a la cuenta destino
              </span>

              <strong
                class="monto ingreso"
                id="tr-v-entra"
              >
                $ 0
              </strong>
            </div>
          </div>
        </div>

        <p class="nota">
          No cuenta como ingreso ni gasto
          en tu resumen. Algunas transferencias
          entre cuentas propias pueden estar exentas
          de GMF.
        </p>

        <p
          class="error-form"
          id="tr-error"
          role="alert"
        ></p>
      </div>

      <div class="pie-form">
        <small>
          Sin conexión se guarda en el celular
          y se envía después con el mismo identificador.
        </small>

        <button
          class="btn btn-primario"
          type="submit"
        >
          Confirmar transferencia
        </button>
      </div>
    </form>
  `;

  const form = c.querySelector('#form-tr');
  const monto = c.querySelector('#tr-monto');
  const origen = c.querySelector('#tr-origen');
  const destino = c.querySelector('#tr-destino');
  const gmf = c.querySelector('#tr-gmf');
  const error = c.querySelector('#tr-error');

  const valorMonto = () =>
    Number(
      monto.value.replace(/\D/g, '')
    );

  const nombre = id =>
    cuentas.find(
      x =>
        String(x.id_cuenta) === String(id)
    )?.nombre_cuenta || '';


  // ------------------------------------
  // VISTA PREVIA FINANCIERA
  // ------------------------------------

  function recalcular() {
    const m = valorMonto();

    const g = gmf.checked
      ? Math.round(
          m * TASA_GMF * 100
        ) / 100
      : 0;

    c.querySelector('#tr-v-gmf')
      .textContent = monedaExacta(g);

    c.querySelector('#tr-v-sale')
      .textContent = '− ' + monedaExacta(m + g);

    c.querySelector('#tr-v-entra')
      .textContent = '+ ' + monedaExacta(m);

    c.querySelector('#tr-t-sale')
      .textContent =
        `Sale de ${
          nombre(origen.value) ||
          'la cuenta origen'
        }`;

    c.querySelector('#tr-t-entra')
      .textContent =
        `Entra a ${
          nombre(destino.value) ||
          'la cuenta destino'
        }`;

    pintarSaldoTransferencia(m, g);
  }


  function pintarOpcionesCuenta() {
    const anteriorOrigen = origen.value;
    const anteriorDestino = destino.value;

    origen.innerHTML = cuentas.map(cu => {
      const r = encontrarSaldoReserva(
        consulta,
        cu.id_cuenta
      );

      const libre = r
        ? cop(
            Number(cu.saldo_actual) -
            Number(r.monto_reservado)
          )
        : 'por verificar';

      return `
        <option value="${
          Number(cu.id_cuenta)
        }">
          ${esc(cu.nombre_cuenta)}
          · Libre ${esc(libre)}
        </option>
      `;
    }).join('');

    destino.innerHTML = cuentas.map(cu => `
      <option value="${Number(cu.id_cuenta)}">
        ${esc(cu.nombre_cuenta)}
        · Saldo ${cop(cu.saldo_actual)}
      </option>
    `).join('');

    if (cuentas.some(
      cu =>
        String(cu.id_cuenta) ===
        anteriorOrigen
    )) {
      origen.value = anteriorOrigen;
    }

    if (cuentas.some(
      cu =>
        String(cu.id_cuenta) ===
        anteriorDestino
    )) {
      destino.value = anteriorDestino;

    } else if (cuentas.length >= 2) {
      destino.value = String(
        cuentas.find(
          cu =>
            String(cu.id_cuenta) !== origen.value
        )?.id_cuenta || ''
      );
    }
  }


  function pintarSaldoTransferencia(m, g) {
    const el = c.querySelector('#tr-saldos');

    if (!el) return;

    const cuOrigen = cuentas.find(
      cu =>
        String(cu.id_cuenta) === origen.value
    );

    const cuDestino = cuentas.find(
      cu =>
        String(cu.id_cuenta) === destino.value
    );

    if (!cuOrigen || !cuDestino) {
      el.textContent =
        'Selecciona cuentas válidas ' +
        'para consultar los saldos.';

      return;
    }

    const real = Number(
      cuOrigen.saldo_actual
    );

    const r = encontrarSaldoReserva(
      consulta,
      cuOrigen.id_cuenta
    );

    const reservado = r
      ? Number(r.monto_reservado)
      : null;

    const libre = reservado === null
      ? null
      : real - reservado;

    const debito = m + g;

    const excede =
      libre !== null &&
      debito > libre;

    const origenAviso = cuentasDesdeCache
      ? 'Cuentas guardadas. '
      : '';

    el.innerHTML = `
      <div class="fila">
        <span>Origen · Saldo real</span>
        <strong class="monto">
          ${cop(real)}
        </strong>
      </div>

      <div class="fila">
        <span>Origen · Reservado</span>
        <strong class="monto">
          ${
            reservado === null
              ? 'Sin verificar'
              : cop(reservado)
          }
        </strong>
      </div>

      <div class="fila principal">
        <span>Origen · Libre</span>
        <strong class="monto">
          ${
            libre === null
              ? 'Sin verificar'
              : cop(libre)
          }
        </strong>
      </div>

      <div class="fila">
        <span>Salida con GMF</span>
        <strong class="monto">
          ${monedaExacta(debito)}
        </strong>
      </div>

      <div class="fila principal">
        <span>Libre después (estimado)</span>

        <strong class="monto">
          ${
            libre === null
              ? 'Sin verificar'
              : monedaExacta(libre - debito)
          }
        </strong>
      </div>

      <div class="fila">
        <span>Destino · Saldo real</span>
        <strong class="monto">
          ${cop(cuDestino.saldo_actual)}
        </strong>
      </div>

      <div class="fila">
        <span>
          Destino · Saldo después (estimado)
        </span>

        <strong class="monto">
          ${
            cop(
              Number(cuDestino.saldo_actual) + m
            )
          }
        </strong>
      </div>

      ${
        excede
          ? `
            <div class="aviso">
              El total de salida supera el saldo libre.
              Reduce el monto o libera reservas desde Metas.
            </div>
          `
          : ''
      }

      <p class="fuente">
        ${
          esc(
            origenAviso +
            textoEstadoSaldo(consulta)
          )
        }

        Si estás offline, solo se guardará
        una operación pendiente.
      </p>
    `;
  }


  // ------------------------------------
  // EVENTOS DE FORMULARIO
  // ------------------------------------

  monto.addEventListener('input', () => {
    const digitos = monto.value
      .replace(/\D/g, '')
      .slice(0, 13);

    monto.value = digitos
      ? cop(digitos)
      : '';

    recalcular();
  });

  [origen, destino, gmf].forEach(el => {
    el.addEventListener(
      'change',
      recalcular
    );
  });

  c.querySelector('#tr-cambiar')
    .addEventListener('click', () => {
      const a = origen.value;

      origen.value = destino.value;
      destino.value = a;

      recalcular();
    });


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
        'No fue posible consultar el saldo libre:',
        e
      );
    }

    if (!mismaSesion()) return;

    pintarOpcionesCuenta();

    if (cuentas.length < 2) {
      error.textContent =
        'Necesitas al menos dos cuentas activas ' +
        'para transferir.';

      form.querySelector(
        'button[type="submit"]'
      ).disabled = true;
    }

  } catch (e) {
    origen.innerHTML = `
      <option value="">
        Sin cuentas
      </option>
    `;

    destino.innerHTML = origen.innerHTML;
    error.textContent = e.message;
  }

  recalcular();


  // ------------------------------------
  // GUARDAR TRANSFERENCIA
  // ------------------------------------

  form.addEventListener('submit', async ev => {
    ev.preventDefault();
    error.textContent = '';

    const m = valorMonto();

    if (!m) {
      error.textContent =
        'Escribe un monto mayor a cero.';

      monto.focus();
      return;
    }

    if (!origen.value || !destino.value) {
      error.textContent =
        'Elige las dos cuentas.';
      return;
    }

    if (origen.value === destino.value) {
      error.textContent =
        'La cuenta de origen y la de destino ' +
        'deben ser diferentes.';

      return;
    }

    if (
      !form.fecha.value ||
      form.fecha.value > hoyISO()
    ) {
      error.textContent =
        'La fecha no puede ser futura.';
      return;
    }

    const datos = {
      uuid_operacion: uuidOperacion,
      id_cuenta_origen: Number(origen.value),
      id_cuenta_destino: Number(destino.value),
      monto: m,
      fecha_transferencia: form.fecha.value,
      aplica_gmf: gmf.checked
    };

    const motivo = form.motivo.value.trim();

    if (motivo) {
      datos.motivo = motivo;
    }

    const contenido = JSON.stringify(datos);

    if (
      datosIntento !== null &&
      datosIntento !== contenido
    ) {
      error.textContent =
        'Esta transferencia ya fue intentada ' +
        'con otros datos. Revisa Movimientos ' +
        'antes de cambiarla.';

      return;
    }

    if (datosIntento === null) {
      datosIntento = contenido;
    }

    const boton = form.querySelector(
      'button[type="submit"]'
    );

    if (boton.disabled) return;

    boton.disabled = true;
    boton.textContent =
      'Guardando transferencia…';


    // PASO 1: guardar primero en IndexedDB.

    try {
      await guardarOffline(
        'TRANSFERENCIA',
        uuidOperacion,
        datos
      );

    } catch (e) {
      error.textContent =
        'No fue posible guardar la transferencia ' +
        'en el dispositivo: ' +
        e.message;

      boton.disabled = false;
      boton.textContent = 'Confirmar transferencia';

      return;
    }


    // PASO 2: sincronizar si hay conexión.

    let resumenSync = null;

    if (navigator.onLine) {
      boton.textContent = 'Sincronizando…';

      try {
        resumenSync = await sincronizar();

      } catch (e) {
        console.warn(
          'La sincronización no terminó:',
          e
        );
      }
    }


    // PASO 3: consultar la operación local.

    let operacionLocal;
    let lecturaCorrecta = false;

    try {
      const todas = await obtenerOperacionesLocales();

      if (!Array.isArray(todas)) {
        throw new Error(
          'Respuesta local inválida'
        );
      }

      operacionLocal = todas.find(
        op => op.uuid_operacion === uuidOperacion
      );

      lecturaCorrecta = true;

    } catch (e) {
      console.warn(
        'No fue posible leer la cola local:',
        e
      );
    }


    // PASO 4: informar sin inventar confirmaciones.

    if (!lecturaCorrecta) {
      aviso(
        'La transferencia quedó guardada. ' +
        'No se pudo verificar su estado actual. ' +
        'Revísala en Movimientos antes de repetirla.',
        'alerta'
      );

    } else if (
      operacionLocal?.estado_sync === 'ERROR'
    ) {
      aviso(
        'El servidor rechazó la transferencia. ' +
        'Revísala en Movimientos.',
        'alerta'
      );

    } else if (operacionLocal) {
      aviso(
        'Transferencia guardada en el dispositivo. ' +
        'Está pendiente de sincronización.',
        'alerta'
      );

    } else if (
      resumenSync?.sincronizadas > 0
    ) {
      aviso(
        'Sincronización completada. ' +
        'Consulta el historial de transferencias.',
        'ok'
      );

    } else {
      aviso(
        'La transferencia ya no figura pendiente. ' +
        'Verifica su resultado en el historial.',
        'alerta'
      );
    }

    location.hash = '#/inicio';
  });
}
