
import {
  obtenerPlanificacion,
  obtenerMisCuentas,
  crearObligacion,
  obtenerObligacion,
  actualizarObligacion,
  desactivarObligacion,
  ErrorDeRed
} from '../api.js';

import { obtenerUsuario } from '../sesion.js';

import {
  obtenerOperacionesLocales
} from '../offline-db.js';

import {
  cop,
  esc,
  hoyISO,
  nuevoUUID,
  aviso,
  guardarCache,
  leerCache
} from '../util.js';

import {
  cargando,
  errorCarga
} from './comun.js';


export async function render(c) {
  let ocupada = false;
  let obligaciones = [];
  let obligacionEditando = null;

  c.innerHTML = `
    <style>
      .obl-encabezado-lista {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
      }

      .obl-boton-nuevo {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        border: 0;
        border-radius: 100px;
        background: var(--c-bg-087a59);
        color: var(--c-tx-ffffff);
        padding: 11px 16px;
        font: inherit;
        font-size: 14px;
        font-weight: 700;
        cursor: pointer;
      }

      .obl-boton-nuevo:disabled {
        opacity: .5;
        cursor: not-allowed;
      }

      .obl-acciones {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
        margin-top: 14px;
      }

      .obl-mensaje:empty {
        display: none;
      }

      .obl-modal {
        box-sizing: border-box;
        width: min(94vw, 510px);
        max-width: 510px;
        max-height: 88dvh;
        margin: auto;
        padding: 0;
        border: 0;
        border-radius: 22px;
        background: var(--c-bg-ffffff);
        color: var(--c-tx-17251f);
        box-shadow: 0 18px 60px rgba(0, 0, 0, .2);
        overflow: hidden;
      }

      .obl-modal[open] {
        display: flex;
        flex-direction: column;
      }

      .obl-modal::backdrop {
        background: rgba(0, 0, 0, .55);
      }

      .obl-modal-form {
        display: flex;
        flex-direction: column;
        min-height: 0;
        max-height: 88dvh;
        margin: 0;
      }

      .obl-modal-cabecera {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 19px 22px;
        border-bottom: 1px solid var(--c-bd-e7ece9);
        flex-shrink: 0;
      }

      .obl-modal-cabecera h2 {
        margin: 0;
        font-size: 21px;
      }

      .obl-modal-cerrar {
        display: grid;
        place-items: center;
        flex-shrink: 0;
        width: 36px;
        height: 36px;
        border: 0;
        border-radius: 50%;
        background: var(--c-bg-f0f2f1);
        color: var(--c-tx-25342d);
        font-size: 24px;
        cursor: pointer;
      }

      .obl-modal-cuerpo {
        overflow-y: auto;
        overscroll-behavior: contain;
        min-height: 0;
        padding: 22px;
      }

      .obl-modal-cuerpo .campo {
        margin-bottom: 15px;
      }

      .obl-modal-cuerpo .campo input,
      .obl-modal-cuerpo .campo select,
      .obl-modal-cuerpo .campo textarea {
        box-sizing: border-box;
        display: block;
        width: 100%;
        max-width: 100%;
        padding: 13px 15px;
        background: var(--c-bg-f1f3f2);
        border: 1px solid transparent;
        border-radius: 15px;
        color: var(--c-tx-17251f);
        font: inherit;
      }

      .obl-modal-cuerpo .campo textarea {
        min-height: 80px;
        resize: vertical;
      }

      .obl-modal-cuerpo .campo input:focus,
      .obl-modal-cuerpo .campo select:focus,
      .obl-modal-cuerpo .campo textarea:focus {
        outline: 2px solid var(--c-bd-087a59);
      }

      .obl-modal-nota {
        padding: 12px;
        border-radius: 12px;
        background: var(--c-bg-e2f3eb);
        color: var(--c-tx-07533e);
        font-size: 13px;
        line-height: 1.5;
      }

      .obl-modal-error {
        color: var(--c-tx-b42318);
        font-size: 13px;
        margin-top: 12px;
      }

      .obl-modal-error:empty {
        display: none;
      }

      .obl-modal-pie {
        display: flex;
        gap: 10px;
        flex-shrink: 0;
        padding: 15px 22px;
        border-top: 1px solid var(--c-bd-e7ece9);
      }

      .obl-modal-pie button {
        flex: 1;
        min-width: 0;
      }

      .obl-modal-pie button:disabled {
        opacity: .45;
        cursor: not-allowed;
      }

      .obl-grupo-inicial {
        margin: 16px 0;
        padding: 15px;
        border-radius: 15px;
        background: var(--c-bg-f1f7f4);
      }

      .obl-grupo-inicial[hidden] {
        display: none;
      }

      .obl-grupo-inicial .campo {
        margin-bottom: 12px;
      }

      .obl-checkbox {
        display: flex;
        align-items: center;
        gap: 9px;
        font-size: 14px;
      }

      .obl-checkbox[hidden] {
        display: none;
      }

      .obl-checkbox input {
        width: auto !important;
        margin: 0;
      }

      .obl-obligatorio {
        display: inline-block;
        margin-bottom: 7px;
        color: var(--c-tx-07533e);
        font-weight: 700;
      }

      .obl-obligatorio-nota {
        margin-top: 7px;
        font-size: 12px;
        color: var(--c-tx-52645a);
      }

      @media (max-width: 430px) {
        .obl-modal {
          width: calc(100vw - 20px);
          border-radius: 18px;
        }

        .obl-modal-cabecera,
        .obl-modal-cuerpo {
          padding: 16px;
        }

        .obl-modal-pie {
          padding: 12px 16px;
        }

        .obl-boton-nuevo {
          padding: 10px 13px;
        }
      }
    </style>


    <header class="banda">
      <div class="banda-fila espaciada">
        <h1 class="banda-titulo">
          Deudas y préstamos
        </h1>
      </div>

      <div class="totales" id="totales"></div>
    </header>


    <section class="seccion">
      <div class="obl-encabezado-lista">
        <h2>Mis obligaciones</h2>

        <button
          type="button"
          id="obl-nueva"
          class="obl-boton-nuevo"
        >
          + Nueva obligación
        </button>
      </div>

      <p
        id="obl-mensaje"
        class="error-form obl-mensaje"
        role="status"
        aria-live="polite"
      ></p>
    </section>


    <div id="cuerpo">
      ${cargando()}
    </div>


    <dialog
      id="obl-modal"
      class="obl-modal"
      aria-labelledby="obl-modal-titulo"
    ></dialog>
  `;

  const cuerpo = c.querySelector('#cuerpo');
  const totales = c.querySelector('#totales');
  const mensaje = c.querySelector('#obl-mensaje');
  const modal = c.querySelector('#obl-modal');
  const botonNuevo = c.querySelector('#obl-nueva');

  const limpiar = valor =>
    String(valor ?? '').trim().replace(/\s+/g, ' ');


  function montoValido(valor) {
    return (
      /^(?:0|[1-9]\d{0,12})(?:\.\d{1,2})?$/.test(valor) &&
      Number(valor) > 0
    );
  }


  function mostrarError(error, destino = mensaje) {
    destino.textContent =
      error instanceof ErrorDeRed
        ? (
            'No se recibió confirmación. ' +
            'Comprueba si la obligación fue creada ' +
            'antes de volver a intentarlo.'
          )
        : (
            error?.message ||
            'No se pudo completar la operación.'
          );
  }


  function cerrarModal() {
    if (modal.open) {
      modal.close();
    }

    obligacionEditando = null;
  }


  // -------------------------------------
  // CARGAR OBLIGACIONES
  // -------------------------------------

  async function cargarObligaciones() {
    let plan;
    let desdeCache = false;

    try {
      plan = await obtenerPlanificacion();

      if (!Array.isArray(plan?.obligaciones)) {
        throw new Error(
          'El servidor devolvió datos inválidos.'
        );
      }

      guardarCache('planificacion', plan);

    } catch (error) {
      const cache = leerCache('planificacion');

      if (
        error instanceof ErrorDeRed &&
        Array.isArray(cache?.datos?.obligaciones)
      ) {
        plan = cache.datos;
        desdeCache = true;

      } else {
        cuerpo.innerHTML = errorCarga(error);
        totales.innerHTML = '';
        return;
      }
    }

    obligaciones = plan.obligaciones;

    const activas = obligaciones.filter(
      o => o.estado === 'ACTIVA'
    );


    function sumar(tipo) {
      return activas
        .filter(o => o.tipo_obligacion === tipo)
        .reduce(
          (total, o) =>
            total + Number(o.monto_pendiente || 0),
          0
        );
    }


    function contar(tipo) {
      return activas.filter(
        o => o.tipo_obligacion === tipo
      ).length;
    }


    totales.innerHTML = `
      <div class="total">
        <span>Debes</span>

        <strong class="monto">
          ${cop(sumar('POR_PAGAR'))}
        </strong>

        <small>
          ${contar('POR_PAGAR')} activa(s)
        </small>
      </div>

      <div class="total">
        <span>Te deben</span>

        <strong class="monto">
          ${cop(sumar('POR_COBRAR'))}
        </strong>

        <small>
          ${contar('POR_COBRAR')} activa(s)
        </small>
      </div>
    `;


    function tarjeta(o) {
      const id = Number(o.id_obligacion);
      const original = Number(o.monto_original || 0);
      const abonado = Number(o.total_abonado || 0);

      const porcentaje = original > 0
        ? Math.max(
            0,
            Math.min(
              100,
              Math.round(abonado / original * 100)
            )
          )
        : 0;

      const porPagar =
        o.tipo_obligacion === 'POR_PAGAR';

      const activa = o.estado === 'ACTIVA';

      return `
        <article
          class="tarjeta-gris obligacion${
            activa ? '' : ' cerrada'
          }"
        >
          <div class="obl-cabeza">
            <strong>
              ${esc(o.nombre_obligacion)}
            </strong>

            <span class="etiqueta">
              ${esc(o.estado)}
            </span>
          </div>

          <div class="obl-cifra">
            <span>
              ${porPagar ? 'Lo que debes' : 'Te falta cobrar'}
            </span>

            <strong class="monto">
              ${cop(o.monto_pendiente)}
            </strong>
          </div>

          <div
            class="barra"
            role="img"
            aria-label="${porcentaje}% completado"
          >
            <span style="width:${porcentaje}%"></span>
          </div>

          <div class="resumen-pie">
            <span>
              ${porPagar ? 'Pagado' : 'Cobrado'}

              <span class="monto">
                ${cop(abonado)}
              </span>
            </span>

            <span>
              de

              <span class="monto">
                ${cop(original)}
              </span>
            </span>
          </div>

          ${
            activa
              ? `
                <div class="obl-acciones">

                  <a
                    class="btn btn-primario btn-chico"
                    href="#/abonar/${id}"
                  >
                    ${
                      porPagar
                        ? 'Registrar pago'
                        : 'Registrar cobro'
                    }
                  </a>

                  <button
                    type="button"
                    class="btn"
                    data-obl-accion="editar"
                    data-id="${id}"
                  >
                    Editar
                  </button>

                  <button
                    type="button"
                    class="btn"
                    data-obl-accion="desactivar"
                    data-id="${id}"
                  >
                    Desactivar
                  </button>
                </div>
              `
              : `
                <p class="nota">
                  Registro conservado para el historial.
                </p>
              `
          }
        </article>
      `;
    }


    function grupo(titulo, tipo) {
      const lista = obligaciones.filter(
        o => o.tipo_obligacion === tipo
      );

      if (!lista.length) return '';

      return `
        <section class="seccion">
          <div class="seccion-titulo">
            <h2>${titulo}</h2>
          </div>

          ${lista.map(tarjeta).join('')}
        </section>
      `;
    }


    cuerpo.innerHTML = `
      ${
        desdeCache
          ? `
            <section class="seccion">
              <p class="nota">
                Sin conexión: mostrando los últimos
                datos guardados. Administrar
                obligaciones requiere Internet.
              </p>
            </section>
          `
          : ''
      }

      ${
        obligaciones.length
          ? (
              grupo('Por pagar', 'POR_PAGAR') +
              grupo('Por cobrar', 'POR_COBRAR')
            )
          : `
            <section class="seccion">
              <p class="vacio">
                Aún no tienes obligaciones registradas.
                Utiliza Nueva obligación para comenzar.
              </p>
            </section>
          `
      }
    `;
  }


  // -------------------------------------
  // MOSTRAR FORMULARIO MODAL
  // -------------------------------------

  function abrirFormulario(modo, datos = null) {
    const editando = modo === 'editar';

    const nombre = editando
      ? datos.nombre_obligacion
      : '';

    const vencimiento = editando
      ? (datos.fecha_vencimiento || '')
      : '';

    const descripcion = editando
      ? (datos.descripcion || '')
      : '';

    const uuidInicial = editando
      ? ''
      : nuevoUUID();

    modal.innerHTML = `
      <form
        id="obl-form-modal"
        class="obl-modal-form"
        data-modo="${modo}"
        data-id="${editando ? Number(datos.id_obligacion) : ''}"
        data-uuid-inicial="${uuidInicial}"
        novalidate
      >

        <div class="obl-modal-cabecera">
          <h2 id="obl-modal-titulo">
            ${
              editando
                ? 'Editar obligación'
                : 'Nueva obligación'
            }
          </h2>

          <button
            type="button"
            class="obl-modal-cerrar"
            data-cerrar-modal
            aria-label="Cerrar formulario"
          >
            ×
          </button>
        </div>


        <div class="obl-modal-cuerpo">

          <div class="campo">
            <label for="obl-nombre">
              Nombre de la obligación
            </label>

            <input
              id="obl-nombre"
              name="nombre_obligacion"
              maxlength="80"
              value="${esc(nombre)}"
              placeholder="Ej. Préstamo familiar"
              required
            >
          </div>


          ${
            editando
              ? `
                <p class="obl-modal-nota">
                  Tipo:
                  ${
                    datos.tipo_obligacion === 'POR_PAGAR'
                      ? 'Dinero que debo'
                      : 'Dinero que me deben'
                  }

                  <br>

                  Monto original:
                  ${cop(datos.monto_original)}

                  <br>

                  Fecha de inicio:
                  ${esc(datos.fecha_inicio)}

                  <br><br>

                  El capital y la fecha inicial
                  no pueden modificarse.
                </p>
              `
              : `
                <div class="campo">
                  <label for="obl-tipo">
                    Tipo de obligación
                  </label>

                  <select
                    id="obl-tipo"
                    name="tipo_obligacion"
                    required
                  >
                    <option value="POR_PAGAR">
                      Dinero que debo
                    </option>

                    <option value="POR_COBRAR">
                      Dinero que me deben
                    </option>
                  </select>
                </div>


                <!-- DECISIÓN OBLIGATORIA -->
                <div class="campo">
                  <label
                    for="obl-hubo-dinero"
                    class="obl-obligatorio"
                  >
                    ¿Hubo movimiento inicial de dinero? *
                  </label>

                  <select
                    id="obl-hubo-dinero"
                    name="registrar_movimiento_inicial"
                    required
                  >
                    <option value="" selected disabled>
                      Selecciona una opción…
                    </option>

                    <option value="si">
                      Sí, registrar dinero en una cuenta
                    </option>

                    <option value="no">
                      No, solo registrar la obligación
                    </option>
                  </select>

                  <p class="obl-obligatorio-nota">
                    Debes seleccionar una opción
                    antes de crear la obligación.
                  </p>
                </div>


                <div
                  id="obl-dinero-inicial"
                  class="obl-grupo-inicial"
                  hidden
                >
                  <div class="campo">
                    <label for="obl-cuenta-inicial">
                      <span id="obl-texto-cuenta">
                        Cuenta financiera
                      </span>
                    </label>

                    <select
                      id="obl-cuenta-inicial"
                      name="id_cuenta_inicial"
                    >
                      <option value="">
                        Selecciona una cuenta
                      </option>
                    </select>
                  </div>

                  <label
                    class="obl-checkbox"
                    id="obl-gmf-fila"
                    hidden
                  >
                    <input
                      id="obl-gmf-inicial"
                      name="aplica_gmf_inicial"
                      type="checkbox"
                    >

                    Aplicar GMF (4 × 1000)
                    a la salida de dinero
                  </label>

                  <p
                    id="obl-ayuda-inicial"
                    class="nota"
                  ></p>
                </div>


                <div class="campo">
                  <label for="obl-monto">
                    Monto original (COP)
                  </label>

                  <input
                    id="obl-monto"
                    name="monto_original"
                    inputmode="decimal"
                    placeholder="10000.00"
                    required
                  >
                </div>


                <div class="campo">
                  <label for="obl-inicio">
                    Fecha de inicio
                  </label>

                  <input
                    id="obl-inicio"
                    name="fecha_inicio"
                    type="date"
                    max="${hoyISO()}"
                    value="${hoyISO()}"
                    required
                  >
                </div>
              `
          }


          <div class="campo">
            <label for="obl-vencimiento">
              Fecha de vencimiento (opcional)
            </label>

            <input
              id="obl-vencimiento"
              name="fecha_vencimiento"
              type="date"
              value="${esc(vencimiento)}"
            >
          </div>


          <div class="campo">
            <label for="obl-descripcion">
              Descripción (opcional)
            </label>

            <textarea
              id="obl-descripcion"
              name="descripcion"
              maxlength="255"
              rows="3"
              placeholder="Información adicional"
            >${esc(descripcion)}</textarea>
          </div>


          ${
            editando
              ? ''
              : `
                <p class="obl-modal-nota">
                  Si esta obligación es antigua y el dinero
                  ya está reflejado en tus saldos iniciales,
                  selecciona «No» para evitar duplicarlo.
                </p>
              `
          }

          <p
            id="obl-modal-error"
            class="obl-modal-error"
            role="alert"
          ></p>

        </div>


        <div class="obl-modal-pie">
          <button
            type="button"
            class="btn"
            data-cerrar-modal
          >
            Cancelar
          </button>

          <button
            type="submit"
            class="btn btn-primario"
            ${editando ? '' : 'disabled'}
          >
            ${
              editando
                ? 'Guardar cambios'
                : 'Crear obligación'
            }
          </button>
        </div>
      </form>
    `;

    if (modal.open) {
      modal.close();
    }

    modal.showModal();

    modal.querySelector(
      '[name="nombre_obligacion"]'
    )?.focus();
  }


  // -------------------------------------
  // CARGAR CUENTAS PARA DINERO INICIAL
  // -------------------------------------

  async function cargarCuentasIniciales(form) {
    const selector = form.querySelector(
      '#obl-cuenta-inicial'
    );

    if (!selector) return;

    selector.innerHTML = `
      <option value="">
        Cargando cuentas…
      </option>
    `;

    try {
      const respuesta = await obtenerMisCuentas();

      if (!Array.isArray(respuesta?.cuentas)) {
        throw new Error(
          'No se pudieron consultar las cuentas.'
        );
      }

      const activas = respuesta.cuentas.filter(
        cuenta => cuenta.estado === 'ACTIVA'
      );

      if (activas.length === 0) {
        selector.innerHTML = `
          <option value="">
            No tienes cuentas activas
          </option>
        `;
        return;
      }

      selector.innerHTML = `
        <option value="">
          Selecciona una cuenta
        </option>

        ${activas.map(cuenta => `
          <option value="${Number(cuenta.id_cuenta)}">
            ${esc(cuenta.nombre_cuenta)}
            · ${cop(cuenta.saldo_actual)}
          </option>
        `).join('')}
      `;

    } catch (error) {
      selector.innerHTML = `
        <option value="">
          No fue posible cargar las cuentas
        </option>
      `;

      const destino = form.querySelector(
        '#obl-modal-error'
      );

      if (destino) {
        mostrarError(error, destino);
      }
    }
  }


  // -------------------------------------
  // VALIDAR LA SELECCIÓN OBLIGATORIA
  // -------------------------------------

  async function actualizarDineroInicial(form) {
    const selectorDecision = form.querySelector(
      '#obl-hubo-dinero'
    );

    if (!selectorDecision) return;

    const decision = selectorDecision.value;

    const decisionValida =
      decision === 'si' || decision === 'no';

    const botonGuardar = form.querySelector(
      'button[type="submit"]'
    );

    // Nunca permitir la creación sin decidir.
    botonGuardar.disabled = !decisionValida;

    const bloque = form.querySelector(
      '#obl-dinero-inicial'
    );

    const huboDinero = decision === 'si';

    bloque.hidden = !huboDinero;

    if (!huboDinero) {
      const selectorCuenta = form.querySelector(
        '#obl-cuenta-inicial'
      );

      if (selectorCuenta) {
        selectorCuenta.value = '';
      }

      form.elements.aplica_gmf_inicial.checked = false;
      return;
    }

    const tipo = form.elements.tipo_obligacion.value;
    const prestaste = tipo === 'POR_COBRAR';

    form.querySelector('#obl-texto-cuenta')
      .textContent = prestaste
        ? '¿Desde qué cuenta entregaste el dinero?'
        : '¿En qué cuenta recibiste el dinero?';

    form.querySelector('#obl-ayuda-inicial')
      .textContent = prestaste
        ? (
            'El monto original saldrá de la cuenta ' +
            'seleccionada y quedará por cobrar.'
          )
        : (
            'El monto original entrará a la cuenta ' +
            'seleccionada y quedará por pagar.'
          );

    const filaGMF = form.querySelector(
      '#obl-gmf-fila'
    );

    filaGMF.hidden = !prestaste;

    if (!prestaste) {
      form.elements.aplica_gmf_inicial.checked = false;
    }

    // Descargar cuentas una sola vez al abrir
    // el bloque del movimiento inicial.
    if (form.dataset.cuentasCargadas !== 'si') {
      form.dataset.cuentasCargadas = 'si';
      await cargarCuentasIniciales(form);
    }
  }


  // -------------------------------------
  // ABRIR NUEVA OBLIGACIÓN
  // -------------------------------------

  botonNuevo.addEventListener('click', () => {
    if (ocupada) return;

    mensaje.textContent = '';
    obligacionEditando = null;

    abrirFormulario('crear');
  });


  // -------------------------------------
  // CAMBIAR TIPO O MOVIMIENTO INICIAL
  // -------------------------------------

  modal.addEventListener('change', async ev => {
    const form = modal.querySelector(
      '#obl-form-modal'
    );

    if (
      !form ||
      form.dataset.modo !== 'crear'
    ) {
      return;
    }

    if (
      ev.target.id === 'obl-hubo-dinero' ||
      ev.target.id === 'obl-tipo'
    ) {
      await actualizarDineroInicial(form);
    }
  });


  // -------------------------------------
  // CERRAR MODAL
  // -------------------------------------

  modal.addEventListener('click', ev => {
    if (ocupada) return;

    if (
      ev.target === modal ||
      ev.target.closest('[data-cerrar-modal]')
    ) {
      cerrarModal();
    }
  });


  modal.addEventListener('cancel', ev => {
    if (ocupada) {
      ev.preventDefault();
    }
  });


  modal.addEventListener('close', () => {
    if (!ocupada) {
      obligacionEditando = null;
    }
  });


  // -------------------------------------
  // CREAR O EDITAR OBLIGACIÓN
  // -------------------------------------

  modal.addEventListener('submit', async ev => {
    const form = ev.target.closest(
      '#obl-form-modal'
    );

    if (!form) return;

    ev.preventDefault();

    if (ocupada) return;

    const error = form.querySelector(
      '#obl-modal-error'
    );

    error.textContent = '';

    const editando =
      form.dataset.modo === 'editar';

    const nombre = limpiar(
      form.elements.nombre_obligacion.value
    );

    const vencimiento =
      form.elements.fecha_vencimiento.value;

    const descripcion =
      form.elements.descripcion.value.trim();

    if (!nombre || nombre.length > 80) {
      error.textContent =
        'Escribe un nombre válido.';
      return;
    }

    let datos;

    if (editando) {
      if (!obligacionEditando) {
        error.textContent =
          'No se encontró la obligación original.';
        return;
      }

      if (
        vencimiento &&
        vencimiento < obligacionEditando.fecha_inicio
      ) {
        error.textContent =
          'El vencimiento no puede ser anterior al inicio.';
        return;
      }

      datos = {
        nombre_obligacion: nombre,
        fecha_vencimiento: vencimiento || null,
        descripcion: descripcion || null
      };

    } else {
      const tipo =
        form.elements.tipo_obligacion.value;

      const decision =
        form.elements.registrar_movimiento_inicial.value;

      // Validación final aunque alguien active
      // manualmente el botón desde DevTools.
      if (!['si', 'no'].includes(decision)) {
        error.textContent =
          'Debes indicar si hubo movimiento inicial de dinero.';
        return;
      }

      const huboDinero = decision === 'si';

      const monto = form.elements.monto_original.value
        .trim()
        .replace(',', '.');

      const inicio =
        form.elements.fecha_inicio.value;

      if (
        !['POR_PAGAR', 'POR_COBRAR'].includes(tipo)
      ) {
        error.textContent =
          'Selecciona un tipo válido.';
        return;
      }

      if (!montoValido(monto)) {
        error.textContent =
          'El monto debe ser mayor a cero, ' +
          'sin separadores de miles y con ' +
          'máximo dos decimales.';
        return;
      }

      if (!inicio || inicio > hoyISO()) {
        error.textContent =
          'La fecha de inicio no puede ser futura.';
        return;
      }

      if (vencimiento && vencimiento < inicio) {
        error.textContent =
          'El vencimiento no puede ser anterior al inicio.';
        return;
      }

      const idCuenta = Number(
        form.elements.id_cuenta_inicial?.value
      );

      if (
        huboDinero &&
        (!Number.isSafeInteger(idCuenta) || idCuenta <= 0)
      ) {
        error.textContent =
          'Selecciona la cuenta donde se movió el dinero.';
        return;
      }

      datos = {
        nombre_obligacion: nombre,
        tipo_obligacion: tipo,
        monto_original: monto,
        fecha_inicio: inicio,
        fecha_vencimiento: vencimiento || null,
        descripcion: descripcion || null,
        registrar_movimiento_inicial: huboDinero,
        id_cuenta_inicial: huboDinero ? idCuenta : null,
        uuid_local_inicial:
          huboDinero ? form.dataset.uuidInicial : null,
        aplica_gmf_inicial:
          huboDinero && tipo === 'POR_COBRAR'
            ? form.elements.aplica_gmf_inicial.checked
            : false
      };
    }

    if (!navigator.onLine) {
      error.textContent =
        'Necesitas conexión para guardar la obligación.';
      return;
    }

    ocupada = true;

    const botones = form.querySelectorAll('button');

    botones.forEach(boton => {
      boton.disabled = true;
    });

    let confirmacionIncierta = false;

    try {
      if (editando) {
        await actualizarObligacion(
          Number(form.dataset.id),
          datos
        );

      } else {
        await crearObligacion(datos);
      }

      cerrarModal();

      aviso(
        editando
          ? 'Obligación actualizada correctamente.'
          : 'Obligación creada. Revisa el saldo de tu cuenta.',
        'ok'
      );

      await cargarObligaciones();

    } catch (errorSolicitud) {
      mostrarError(errorSolicitud, error);

      if (errorSolicitud instanceof ErrorDeRed) {
        confirmacionIncierta = true;
      }

    } finally {
      ocupada = false;

      botones.forEach(boton => {
        if (boton.isConnected) {
          boton.disabled =
            confirmacionIncierta &&
            boton.type === 'submit';
        }
      });
    }
  });


  // -------------------------------------
  // ABRIR EDICIÓN
  // -------------------------------------

  async function abrirEdicion(id) {
    if (ocupada) return;

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para editar.';
      return;
    }

    ocupada = true;
    mensaje.textContent = '';

    try {
      const detalle = await obtenerObligacion(id);

      if (detalle.estado !== 'ACTIVA') {
        throw new Error(
          'Solo se pueden editar obligaciones activas.'
        );
      }

      obligacionEditando = detalle;
      abrirFormulario('editar', detalle);

    } catch (error) {
      mostrarError(error);

    } finally {
      ocupada = false;
    }
  }


  // -------------------------------------
  // REVISAR ABONOS LOCALES
  // -------------------------------------

  async function tieneAbonosLocales(idObligacion) {
    const idUsuario = Number(
      obtenerUsuario()?.id_usuario
    );

    if (
      !Number.isSafeInteger(idUsuario) ||
      idUsuario <= 0
    ) {
      throw new Error(
        'Usuario no identificado.'
      );
    }

    const operaciones =
      await obtenerOperacionesLocales();

    if (!Array.isArray(operaciones)) {
      throw new Error(
        'No se pudo consultar la cola local.'
      );
    }

    return operaciones.some(op =>
      Number(op.usuario_id) === idUsuario &&
      op.tipo_operacion === 'ABONO_OBLIGACION' &&
      ['PENDIENTE', 'ERROR'].includes(
        op.estado_sync
      ) &&
      Number(op.datos?.id_obligacion) === idObligacion
    );
  }


  // -------------------------------------
  // EDITAR O DESACTIVAR
  // -------------------------------------

  cuerpo.addEventListener('click', async ev => {
    const boton = ev.target.closest(
      'button[data-obl-accion]'
    );

    if (!boton || ocupada) return;

    const id = Number(boton.dataset.id);
    const accion = boton.dataset.oblAccion;

    const obligacion = obligaciones.find(
      o => Number(o.id_obligacion) === id
    );

    if (
      !obligacion ||
      obligacion.estado !== 'ACTIVA'
    ) {
      return;
    }

    if (accion === 'editar') {
      await abrirEdicion(id);
      return;
    }

    if (accion !== 'desactivar') return;

    mensaje.textContent = '';

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para desactivar.';
      return;
    }

    try {
      if (await tieneAbonosLocales(id)) {
        mensaje.textContent =
          'Hay abonos pendientes o rechazados. ' +
          'Revísalos en Movimientos.';
        return;
      }

    } catch {
      mensaje.textContent =
        'No se pudieron verificar las operaciones pendientes. ' +
        'No se desactivó la obligación.';
      return;
    }

    const confirmado = window.confirm(
      `¿Desactivar "${obligacion.nombre_obligacion}"?\n\n` +
      'No se permite si existen movimientos ' +
      'financieros activos relacionados.'
    );

    if (!confirmado) return;

    ocupada = true;
    boton.disabled = true;

    try {
      if (await tieneAbonosLocales(id)) {
        throw new Error(
          'Hay abonos locales por resolver.'
        );
      }

      await desactivarObligacion(id);

      aviso(
        'Obligación desactivada correctamente.',
        'ok'
      );

      await cargarObligaciones();

    } catch (error) {
      mostrarError(error);

    } finally {
      ocupada = false;

      if (boton.isConnected) {
        boton.disabled = false;
      }
    }
  });


  await cargarObligaciones();
}
