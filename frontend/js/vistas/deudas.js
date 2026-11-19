
import {
  obtenerPlanificacion,
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

  // -------------------------------------
  // ESTILOS EXCLUSIVOS DEL MODAL
  // -------------------------------------

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
        background: #087a59;
        color: white;
        padding: 11px 16px;
        font: inherit;
        font-size: 14px;
        font-weight: 700;
        cursor: pointer;
      }

      .obl-boton-nuevo:hover {
        background: #066448;
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

      .obl-mensaje {
        margin-top: 10px;
      }

      .obl-modal {
        box-sizing: border-box;
        width: min(94vw, 510px);
        max-width: 510px;
        max-height: min(88dvh, 780px);
        margin: auto;
        padding: 0;
        border: 0;
        border-radius: 22px;
        background: #ffffff;
        color: #17251f;
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
        max-height: min(88dvh, 780px);
        margin: 0;
      }

      .obl-modal-cabecera {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 19px 22px;
        border-bottom: 1px solid #e7ece9;
        flex-shrink: 0;
      }

      .obl-modal-cabecera h2 {
        margin: 0;
        font-size: 21px;
        line-height: 1.3;
      }

      .obl-modal-cerrar {
        display: grid;
        place-items: center;
        flex-shrink: 0;
        width: 36px;
        height: 36px;
        border: 0;
        border-radius: 50%;
        background: #f0f2f1;
        color: #25342d;
        font-size: 24px;
        cursor: pointer;
      }

      .obl-modal-cuerpo {
        min-height: 0;
        overflow-y: auto;
        overscroll-behavior: contain;
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
        background: #f1f3f2;
        border: 1px solid transparent;
        border-radius: 15px;
        padding: 13px 15px;
        color: #17251f;
        font: inherit;
      }

      .obl-modal-cuerpo .campo textarea {
        min-height: 80px;
        resize: vertical;
      }

      .obl-modal-cuerpo .campo input:focus,
      .obl-modal-cuerpo .campo select:focus,
      .obl-modal-cuerpo .campo textarea:focus {
        outline: 2px solid #087a59;
        outline-offset: 1px;
      }

      .obl-modal-nota {
        padding: 12px;
        border-radius: 12px;
        background: #e2f3eb;
        color: #07533e;
        font-size: 13px;
        line-height: 1.5;
      }

      .obl-modal-error {
        color: #b42318;
        font-size: 13px;
        margin-top: 12px;
        line-height: 1.4;
      }

      .obl-modal-error:empty {
        display: none;
      }

      .obl-modal-pie {
        display: flex;
        gap: 10px;
        padding: 15px 22px;
        border-top: 1px solid #e7ece9;
        background: #fff;
        flex-shrink: 0;
      }

      .obl-modal-pie button {
        flex: 1;
        min-width: 0;
      }

      @media (max-width: 430px) {
        .obl-modal {
          width: calc(100vw - 20px);
          border-radius: 18px;
        }

        .obl-modal-cabecera {
          padding: 16px;
        }

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
          <span aria-hidden="true">+</span>
          Nueva obligación
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


  // -------------------------------------
  // FUNCIONES AUXILIARES
  // -------------------------------------

  const limpiar = valor =>
    String(valor ?? '').trim().replace(/\s+/g, ' ');

  function montoValido(valor) {
    return (
      /^(?:0|[1-9]\d{0,12})(?:\.\d{1,2})?$/.test(valor)
      && Number(valor) > 0
    );
  }

  function mostrarError(error, destino = mensaje) {
    destino.textContent =
      error instanceof ErrorDeRed
        ? (
            'No se recibió confirmación del servidor. ' +
            'Comprueba el resultado antes de repetir ' +
            'la operación.'
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
  // CONSULTAR Y MOSTRAR OBLIGACIONES
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

    function sumarPendientes(tipo) {
      return activas
        .filter(o => o.tipo_obligacion === tipo)
        .reduce(
          (suma, o) =>
            suma + Number(o.monto_pendiente || 0),
          0
        );
    }

    function contarActivas(tipo) {
      return activas.filter(
        o => o.tipo_obligacion === tipo
      ).length;
    }

    totales.innerHTML = `
      <div class="total">
        <span>Debes</span>
        <strong class="monto">
          ${cop(sumarPendientes('POR_PAGAR'))}
        </strong>
        <small>
          ${contarActivas('POR_PAGAR')} activa(s)
        </small>
      </div>

      <div class="total">
        <span>Te deben</span>
        <strong class="monto">
          ${cop(sumarPendientes('POR_COBRAR'))}
        </strong>
        <small>
          ${contarActivas('POR_COBRAR')} activa(s)
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
              Math.round((abonado / original) * 100)
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
            <span
              style="width: ${porcentaje}%"
            ></span>
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
                datos guardados. Las acciones de
                administración requieren Internet.
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
                Utiliza «Nueva obligación» para comenzar.
              </p>
            </section>
          `
      }
    `;
  }


  // -------------------------------------
  // ABRIR FORMULARIO EN VENTANA MODAL
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

    modal.innerHTML = `
      <form
        id="obl-form-modal"
        class="obl-modal-form"
        data-modo="${modo}"
        data-id="${editando ? Number(datos.id_obligacion) : ''}"
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

                  Estos datos no pueden modificarse
                  para proteger el historial financiero.
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
                  Crear una obligación permite controlar
                  el dinero que debes o que te deben.
                  No mueve dinero de tus cuentas.
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
  // BOTÓN NUEVA OBLIGACIÓN
  // -------------------------------------

  botonNuevo.addEventListener('click', () => {
    if (ocupada) return;

    mensaje.textContent = '';
    obligacionEditando = null;

    abrirFormulario('crear');
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
    const form = ev.target.closest('#obl-form-modal');

    if (!form) return;

    ev.preventDefault();

    if (ocupada) return;

    const error = form.querySelector(
      '#obl-modal-error'
    );

    error.textContent = '';

    const modo = form.dataset.modo;
    const editando = modo === 'editar';

    const nombre = limpiar(
      form.elements.nombre_obligacion.value
    );

    const vencimiento =
      form.elements.fecha_vencimiento.value;

    const descripcion =
      form.elements.descripcion.value.trim();

    if (!nombre || nombre.length > 80) {
      error.textContent =
        'Escribe un nombre de máximo 80 caracteres.';
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
          'El monto debe ser mayor que cero, ' +
          'sin separadores de miles y con máximo ' +
          'dos decimales.';
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

      datos = {
        nombre_obligacion: nombre,
        tipo_obligacion: tipo,
        monto_original: monto,
        fecha_inicio: inicio,
        fecha_vencimiento: vencimiento || null,
        descripcion: descripcion || null
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
          : 'Obligación creada correctamente.',
        'ok'
      );

      await cargarObligaciones();

    } catch (e) {
      mostrarError(e, error);

      if (e instanceof ErrorDeRed) {
        // No reintentar automáticamente una creación
        // si la respuesta del servidor es incierta.
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

    } catch (e) {
      mostrarError(e);

    } finally {
      ocupada = false;
    }
  }


  // -------------------------------------
  // COMPROBAR ABONOS OFFLINE
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
  // EDITAR O DESACTIVAR DESDE LAS TARJETAS
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
          'Esta obligación tiene abonos pendientes ' +
          'o rechazados. Revísalos en Movimientos.';
        return;
      }
    } catch (e) {
      mensaje.textContent =
        'No se pudo verificar la cola local. ' +
        'Por seguridad no se desactivó.';
      return;
    }

    const confirmado = window.confirm(
      `¿Desactivar "${obligacion.nombre_obligacion}"?\n\n` +
      'Solo es posible si no tiene abonos activos. ' +
      'El historial se conservará.'
    );

    if (!confirmado) return;

    ocupada = true;
    boton.disabled = true;

    try {
      if (await tieneAbonosLocales(id)) {
        throw new Error(
          'Hay abonos locales pendientes por resolver.'
        );
      }

      await desactivarObligacion(id);

      aviso(
        'Obligación desactivada correctamente.',
        'ok'
      );

      await cargarObligaciones();

    } catch (e) {
      mostrarError(e);

    } finally {
      ocupada = false;

      if (boton.isConnected) {
        boton.disabled = false;
      }
    }
  });


  // -------------------------------------
  // CARGA INICIAL
  // -------------------------------------

  await cargarObligaciones();
}
