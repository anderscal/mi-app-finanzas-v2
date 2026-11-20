
import {
  obtenerPlanificacion,
  obtenerPresupuestos,
  obtenerCategorias,
  crearPresupuesto,
  actualizarPresupuesto,
  obtenerMetas,
  obtenerMeta,
  crearMeta,
  actualizarMeta,
  aportarMeta,
  desactivarMeta,
  ErrorDeRed
} from '../api.js';

import { obtenerUsuario } from '../sesion.js';

import {
  cop,
  esc,
  nombreMes,
  hoyISO,
  aviso,
  guardarCache,
  leerCache
} from '../util.js';

import {
  banda,
  cargando,
  errorCarga
} from './comun.js';


export async function render(c) {

  const hoy = new Date();

  let mes = hoy.getMonth() + 1;
  let anio = hoy.getFullYear();

  let presupuestos = [];
  let metas = [];

  let planificacion = {
    presupuestos: [],
    metas: [],
    obligaciones: []
  };

  let ocupada = false;
  let desdeCache = false;

  c.innerHTML = `
    <style>
      .pm-cabecera {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
      }

      .pm-nuevo {
        border: 0;
        border-radius: 999px;
        background: #087a59;
        color: #fff;
        padding: 11px 15px;
        font: inherit;
        font-size: 13px;
        font-weight: 800;
        cursor: pointer;
      }

      .pm-nuevo:disabled,
      .pm-modal button:disabled {
        opacity: .45;
        cursor: not-allowed;
      }

      .pm-periodo {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 110px;
        gap: 10px;
        margin: 16px 0;
      }

      .pm-periodo label {
        display: flex;
        flex-direction: column;
        gap: 5px;
        font-size: 13px;
        font-weight: 700;
      }

      .pm-periodo select,
      .pm-periodo input {
        min-width: 0;
        width: 100%;
        box-sizing: border-box;
      }

      .pm-tarjetas {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .pm-tarjeta {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 16px;
        background: #f3f6f4;
        border-radius: 16px;
      }

      .pm-fila {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 10px;
      }

      .pm-fila strong {
        overflow-wrap: anywhere;
      }

      .pm-etiqueta {
        border-radius: 999px;
        padding: 5px 9px;
        background: #dff1e8;
        color: #087a59;
        font-size: 11px;
        font-weight: 800;
      }

      .pm-etiqueta.alerta {
        background: #fff0cd;
        color: #8a5700;
      }

      .pm-etiqueta.excedido {
        background: #ffe1d8;
        color: #a33721;
      }

      .pm-barra {
        height: 10px;
        background: #dce7e0;
        border-radius: 999px;
        overflow: hidden;
      }

      .pm-barra span {
        display: block;
        height: 100%;
        background: #087a59;
      }

      .pm-barra span.alerta {
        background: #d59a2a;
      }

      .pm-barra span.excedido {
        background: #bf5538;
      }

      .pm-nota {
        font-size: 12px;
        color: #596960;
        line-height: 1.5;
      }

      .pm-acciones {
        display: flex;
        gap: 9px;
        flex-wrap: wrap;
      }

      .pm-acciones button {
        cursor: pointer;
      }

      .pm-resumen {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin-bottom: 14px;
      }

      .pm-resumen div {
        display: flex;
        flex-direction: column;
        gap: 5px;
        padding: 14px;
        background: #f1f5f2;
        border-radius: 14px;
      }

      .pm-resumen span {
        font-size: 12px;
        color: #586960;
      }

      .pm-resumen strong {
        font-size: 17px;
        overflow-wrap: anywhere;
      }

      .pm-error {
        color: #b42318;
        font-size: 13px;
        line-height: 1.5;
      }

      .pm-error:empty {
        display: none;
      }

      .pm-modal {
        width: min(94vw, 500px);
        max-width: 500px;
        max-height: 88dvh;
        box-sizing: border-box;
        border: 0;
        border-radius: 20px;
        padding: 0;
        margin: auto;
        background: #fff;
        color: #17251f;
        overflow: hidden;
        box-shadow: 0 18px 60px rgba(0,0,0,.2);
      }

      .pm-modal[open] {
        display: flex;
        flex-direction: column;
      }

      .pm-modal::backdrop {
        background: rgba(0,0,0,.55);
      }

      .pm-form {
        display: flex;
        flex-direction: column;
        min-height: 0;
        max-height: 88dvh;
        margin: 0;
      }

      .pm-modal-cabeza,
      .pm-modal-pie {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        padding: 16px 20px;
        flex-shrink: 0;
        border-bottom: 1px solid #e5ece8;
      }

      .pm-modal-cabeza h2 {
        margin: 0;
        font-size: 20px;
      }

      .pm-modal-pie {
        border-top: 1px solid #e5ece8;
        border-bottom: 0;
      }

      .pm-modal-pie button {
        flex: 1;
        min-width: 0;
      }

      .pm-cerrar {
        border: 0;
        border-radius: 50%;
        width: 36px;
        height: 36px;
        background: #edf1ef;
        font-size: 23px;
        cursor: pointer;
      }

      .pm-modal-cuerpo {
        padding: 20px;
        overflow-y: auto;
        min-height: 0;
        overscroll-behavior: contain;
      }

      .pm-modal-cuerpo .campo {
        margin-bottom: 15px;
      }

      .pm-modal-cuerpo input,
      .pm-modal-cuerpo select,
      .pm-modal-cuerpo textarea {
        box-sizing: border-box;
        display: block;
        width: 100%;
        max-width: 100%;
      }

      .pm-modal-cuerpo textarea {
        min-height: 75px;
      }

      .pm-modal-nota {
        background: #e3f3ea;
        color: #07533e;
        border-radius: 13px;
        padding: 12px;
        font-size: 13px;
        line-height: 1.5;
        margin-bottom: 14px;
      }

      @media (max-width: 430px) {
        .pm-modal {
          width: calc(100vw - 20px);
        }

        .pm-modal-cabeza,
        .pm-modal-cuerpo,
        .pm-modal-pie {
          padding: 15px;
        }
      }
    </style>

    ${banda('Presupuestos y metas', {
      subtitulo: 'Planifica tus gastos y objetivos de ahorro'
    })}

    <section class="seccion">

      <div class="pm-cabecera">
        <h2>Presupuesto mensual</h2>

        <button
          type="button"
          class="pm-nuevo"
          id="pm-nuevo-pres"
        >
          + Nuevo presupuesto
        </button>
      </div>

      <div class="pm-periodo">

        <label for="pm-mes">
          Mes
          <select id="pm-mes">
            ${Array.from(
              { length: 12 },
              (_, i) => `
                <option value="${i + 1}">
                  ${nombreMes(i + 1)}
                </option>
              `
            ).join('')}
          </select>
        </label>

        <label for="pm-anio">
          Año
          <input
            type="number"
            id="pm-anio"
            min="2000"
            max="9998"
            value="${anio}"
          >
        </label>

      </div>

      <p id="pm-estado" class="nota" hidden></p>

      <div
        id="pm-presupuestos"
        class="pm-tarjetas"
      >
        ${cargando()}
      </div>

    </section>


    <section class="seccion">

      <div class="pm-cabecera">
        <h2>Metas de ahorro</h2>

        <button
          type="button"
          class="pm-nuevo"
          id="pm-nueva-meta"
        >
          + Nueva meta
        </button>
      </div>

      <p class="pm-nota">
        Los aportes de metas registran progreso
        de ahorro. No mueven dinero entre cuentas
        ni modifican el saldo bancario.
      </p>

      <div
        id="pm-metas"
        class="pm-tarjetas"
      >
        ${cargando()}
      </div>

    </section>

    <section class="seccion">
      <p
        id="pm-error"
        class="pm-error"
        role="status"
        aria-live="polite"
      ></p>
    </section>

    <dialog
      id="pm-modal"
      class="pm-modal"
      aria-labelledby="pm-modal-titulo"
    ></dialog>
  `;

  const selectorMes = c.querySelector('#pm-mes');
  const selectorAnio = c.querySelector('#pm-anio');
  const listaPres = c.querySelector('#pm-presupuestos');
  const listaMetas = c.querySelector('#pm-metas');
  const modal = c.querySelector('#pm-modal');
  const mensaje = c.querySelector('#pm-error');
  const estado = c.querySelector('#pm-estado');

  const nuevoPres = c.querySelector('#pm-nuevo-pres');
  const nuevaMeta = c.querySelector('#pm-nueva-meta');


  // ------------------------------------
  // FUNCIONES AUXILIARES
  // ------------------------------------

  function numero(valor) {
    const n = Number(valor);
    return Number.isFinite(n) ? n : 0;
  }

  function montoValido(valor) {
    return (
      /^(?:0|[1-9]\d{0,12})(?:\.\d{1,2})?$/.test(valor) &&
      Number(valor) > 0
    );
  }

  function montoFormulario(form) {
    return form.elements.monto.value
      .trim()
      .replace(',', '.');
  }

  function periodoTexto() {
    return `${nombreMes(mes)} ${anio}`;
  }

  function mostrarError(error, destino = mensaje) {
    destino.textContent =
      error instanceof ErrorDeRed
        ? (
            'No se recibió confirmación. ' +
            'Actualiza los datos antes de intentar ' +
            'de nuevo para evitar duplicados.'
          )
        : (
            error?.message ||
            'No se pudo completar la operación.'
          );
  }

  function metaPorId(id) {
    return metas.find(
      m => Number(m.id_meta) === id
    );
  }

  function presupuestoPorId(id) {
    return presupuestos.find(
      p => Number(p.id_presupuesto) === id
    );
  }

  function porcentajeMeta(id) {
    const calculo = planificacion.metas.find(
      m => Number(m.id_meta) === id
    );

    return calculo
      ? numero(calculo.porcentaje_progreso)
      : null;
  }

  function fechaPorDefecto() {
    const d = new Date();
    d.setMonth(d.getMonth() + 3);

    const dos = n => String(n).padStart(2, '0');

    return (
      `${d.getFullYear()}-` +
      `${dos(d.getMonth() + 1)}-` +
      `${dos(d.getDate())}`
    );
  }

  function cerrarModal() {
    if (modal.open) {
      modal.close();
    }
  }


  // ------------------------------------
  // CARGA DE DATOS + CACHÉ
  // ------------------------------------

  async function conCache(clave, consulta, validar) {
    try {
      const datos = await consulta();

      if (!validar(datos)) {
        throw new Error(
          `Respuesta inválida de ${clave}`
        );
      }

      guardarCache(clave, datos);

      return {
        datos,
        cache: false
      };

    } catch (error) {
      if (error instanceof ErrorDeRed) {
        const guardado = leerCache(clave);

        if (
          guardado &&
          validar(guardado.datos)
        ) {
          return {
            datos: guardado.datos,
            cache: true
          };
        }
      }

      throw error;
    }
  }


  async function cargarTodo() {
    const idUsuario = Number(
      obtenerUsuario()?.id_usuario
    );

    const [
      resultadoPres,
      resultadoPlan,
      resultadoMetas
    ] = await Promise.all([
      conCache(
        'presupuestos',
        obtenerPresupuestos,
        Array.isArray
      ),

      conCache(
        'planificacion',
        obtenerPlanificacion,
        x => (
          Array.isArray(x?.presupuestos) &&
          Array.isArray(x?.metas)
        )
      ),

      conCache(
        'metas',
        obtenerMetas,
        Array.isArray
      )
    ]);

    if (
      !Number.isSafeInteger(idUsuario) ||
      idUsuario <= 0 ||
      Number(obtenerUsuario()?.id_usuario) !== idUsuario
    ) {
      throw new Error(
        'La sesión cambió. Recarga la pantalla.'
      );
    }

    presupuestos = resultadoPres.datos;
    planificacion = resultadoPlan.datos;
    metas = resultadoMetas.datos;

    desdeCache = (
      resultadoPres.cache ||
      resultadoPlan.cache ||
      resultadoMetas.cache
    );

    estado.hidden = !desdeCache;

    if (desdeCache) {
      estado.textContent =
        'Mostrando datos guardados del usuario. ' +
        'Crear y editar requiere conexión.';
    }

    pintarPresupuestos();
    pintarMetas();
  }


  // ------------------------------------
  // TARJETAS DE PRESUPUESTOS
  // ------------------------------------

  function pintarPresupuestos() {
    selectorMes.value = String(mes);
    selectorAnio.value = String(anio);

    const delPeriodo = presupuestos.filter(
      p => (
        Number(p.mes) === mes &&
        Number(p.anio) === anio
      )
    );

    if (!delPeriodo.length) {
      listaPres.innerHTML = `
        <p class="vacio">
          No tienes presupuestos para
          ${esc(periodoTexto())}.
        </p>
      `;
      return;
    }

    const calculos = new Map(
      planificacion.presupuestos.map(
        p => [Number(p.id_presupuesto), p]
      )
    );

    let totalLimites = 0;
    let totalGastado = 0;
    let completo = true;

    const tarjetas = delPeriodo.map(p => {
      const id = Number(p.id_presupuesto);
      const calculo = calculos.get(id);
      const limite = numero(p.monto_limite);

      totalLimites += limite;

      if (!calculo) {
        completo = false;
      } else {
        totalGastado += numero(calculo.gastado);
      }

      const gastado = calculo
        ? numero(calculo.gastado)
        : null;

      const disponible = calculo
        ? numero(calculo.disponible)
        : null;

      const porcentaje = calculo
        ? numero(calculo.porcentaje_usado)
        : null;

      const clase = porcentaje === null
        ? ''
        : porcentaje >= 100
          ? 'excedido'
          : porcentaje >= 90
            ? 'alerta'
            : '';

      const progreso = porcentaje === null
        ? 0
        : Math.min(
            100,
            Math.max(0, porcentaje)
          );

      const etiqueta = porcentaje === null
        ? 'Sin cálculo'
        : porcentaje >= 100
          ? 'Límite alcanzado'
          : porcentaje >= 90
            ? 'Cerca del límite'
            : 'En presupuesto';

      const textoDisponible = disponible === null
        ? 'Gasto pendiente de consultar'
        : disponible >= 0
          ? `Disponible ${cop(disponible)}`
          : `Excedido en ${cop(-disponible)}`;

      return `
        <article class="pm-tarjeta">

          <div class="pm-fila">
            <strong>
              ${esc(
                calculo?.categoria ||
                `Categoría #${p.id_categoria}`
              )}
            </strong>

            <span class="pm-etiqueta ${clase}">
              ${etiqueta}
            </span>
          </div>

          <div class="pm-fila">
            <strong class="monto">
              ${
                gastado === null
                  ? '—'
                  : cop(gastado)
              }
            </strong>

            <span class="pm-nota">
              de ${cop(limite)}
            </span>
          </div>

          <div
            class="pm-barra"
            role="img"
            aria-label="${
              porcentaje === null
                ? 'Sin porcentaje disponible'
                : porcentaje.toFixed(1) + '% utilizado'
            }"
          >
            <span
              class="${clase}"
              style="width:${progreso}%"
            ></span>
          </div>

          <div class="pm-fila">
            <span class="pm-nota">
              ${esc(textoDisponible)}
              ${
                porcentaje === null
                  ? ''
                  : `· ${porcentaje.toFixed(1)}% utilizado`
              }
            </span>

            <button
              type="button"
              class="btn btn-chico"
              data-pres="editar"
              data-id="${id}"
            >
              Editar
            </button>
          </div>

        </article>
      `;
    }).join('');

    listaPres.innerHTML = `
      <div class="pm-resumen">
        <div>
          <span>Límite planificado</span>
          <strong class="monto">
            ${cop(totalLimites)}
          </strong>
        </div>

        <div>
          <span>Gastado del período</span>
          <strong class="monto">
            ${
              completo
                ? cop(totalGastado)
                : 'Pendiente'
            }
          </strong>
        </div>
      </div>

      <div class="pm-tarjetas">
        ${tarjetas}
      </div>
    `;
  }


  // ------------------------------------
  // TARJETAS DE METAS
  // ------------------------------------

  function pintarMetas() {
    if (!metas.length) {
      listaMetas.innerHTML = `
        <p class="vacio">
          Aún no tienes metas.
          Utiliza «Nueva meta» para comenzar.
        </p>
      `;
      return;
    }

    listaMetas.innerHTML = metas.map(meta => {
      const id = Number(meta.id_meta);
      const acumulado = numero(meta.monto_acumulado);
      const objetivo = numero(meta.monto_objetivo);
      const faltante = Math.max(
        0,
        objetivo - acumulado
      );

      const porcentaje = porcentajeMeta(id);

      const progreso = porcentaje === null
        ? 0
        : Math.min(
            100,
            Math.max(0, porcentaje)
          );

      const activa = meta.estado === 'ACTIVA';
      const cumplida = meta.estado === 'CUMPLIDA';

      const etiqueta = cumplida
        ? 'Cumplida'
        : meta.estado === 'INACTIVA'
          ? 'Inactiva'
          : 'En progreso';

      return `
        <article class="pm-tarjeta">

          <div class="pm-fila">
            <strong>
              ${esc(meta.nombre_meta)}
            </strong>

            <span class="pm-etiqueta">
              ${etiqueta}
            </span>
          </div>

          <div class="pm-fila">
            <strong class="monto">
              ${cop(acumulado)}
            </strong>

            <span class="pm-nota">
              de ${cop(objetivo)}
            </span>
          </div>

          <div
            class="pm-barra"
            role="img"
            aria-label="${
              porcentaje === null
                ? 'Porcentaje no disponible'
                : porcentaje.toFixed(1) + '% ahorrado'
            }"
          >
            <span
              style="width:${progreso}%"
            ></span>
          </div>

          <div class="pm-fila">
            <span class="pm-nota">
              ${
                cumplida
                  ? 'Objetivo alcanzado'
                  : `Faltan ${cop(faltante)}`
              }
              ${
                porcentaje === null
                  ? ''
                  : `· ${porcentaje.toFixed(1)}%`
              }
            </span>

            <span class="pm-nota">
              Fecha objetivo:
              ${esc(meta.fecha_objetivo)}
            </span>
          </div>

          ${
            meta.descripcion
              ? `
                <p class="pm-nota">
                  ${esc(meta.descripcion)}
                </p>
              `
              : ''
          }

          ${
            meta.estado !== 'INACTIVA'
              ? `
                <div class="pm-acciones">

                  ${
                    activa
                      ? `
                        <button
                          type="button"
                          class="btn btn-primario btn-chico"
                          data-meta="aportar"
                          data-id="${id}"
                        >
                          Registrar aporte
                        </button>
                      `
                      : ''
                  }

                  <button
                    type="button"
                    class="btn btn-chico"
                    data-meta="editar"
                    data-id="${id}"
                  >
                    Editar
                  </button>

                  ${
                    activa && acumulado === 0
                      ? `
                        <button
                          type="button"
                          class="btn btn-chico"
                          data-meta="desactivar"
                          data-id="${id}"
                        >
                          Desactivar
                        </button>
                      `
                      : ''
                  }

                </div>
              `
              : ''
          }

        </article>
      `;
    }).join('');
  }


  // ------------------------------------
  // VENTANA COMPARTIDA
  // ------------------------------------

  function abrirModal(
    titulo,
    tipo,
    contenido,
    botonTexto,
    atributos = ''
  ) {
    modal.innerHTML = `
      <form
        id="pm-form"
        class="pm-form"
        data-tipo="${tipo}"
        ${atributos}
        novalidate
      >

        <div class="pm-modal-cabeza">
          <h2 id="pm-modal-titulo">
            ${esc(titulo)}
          </h2>

          <button
            type="button"
            class="pm-cerrar"
            data-cerrar
            aria-label="Cerrar"
          >
            ×
          </button>
        </div>

        <div class="pm-modal-cuerpo">
          ${contenido}

          <p
            id="pm-modal-error"
            class="pm-error"
            role="alert"
          ></p>
        </div>

        <div class="pm-modal-pie">
          <button
            type="button"
            class="btn"
            data-cerrar
          >
            Cancelar
          </button>

          <button
            type="submit"
            class="btn btn-primario"
          >
            ${esc(botonTexto)}
          </button>
        </div>

      </form>
    `;

    if (modal.open) {
      modal.close();
    }

    modal.showModal();
  }


  function campoMonto(valor = '') {
    return `
      <div class="campo">
        <label for="pm-monto">
          Monto (COP)
        </label>

        <input
          id="pm-monto"
          name="monto"
          inputmode="decimal"
          autocomplete="off"
          placeholder="Ej. 100000"
          value="${esc(valor)}"
          required
        >

        <small class="ayuda">
          Sin puntos de miles.
          Máximo dos decimales.
        </small>
      </div>
    `;
  }


  // ------------------------------------
  // MODAL CREAR/EDITAR PRESUPUESTO
  // ------------------------------------

  function modalPresupuesto(
    tipo,
    opciones = [],
    presupuesto = null
  ) {
    const editando = tipo === 'pres-editar';

    const id = editando
      ? Number(presupuesto.id_presupuesto)
      : 0;

    const calculo = editando
      ? planificacion.presupuestos.find(
          p => Number(p.id_presupuesto) === id
        )
      : null;

    const nombre = calculo?.categoria ||
      `Categoría #${presupuesto?.id_categoria ?? ''}`;

    const opcionesHTML = opciones.map(cat => `
      <option value="${Number(cat.id_categoria)}">
        ${esc(cat.nombre_categoria)}
      </option>
    `).join('');

    abrirModal(
      editando
        ? 'Editar presupuesto'
        : 'Nuevo presupuesto',
      tipo,
      `
        <p class="pm-modal-nota">
          Período: ${esc(periodoTexto())}
        </p>

        ${
          editando
            ? `
              <p>
                Categoría: <strong>${esc(nombre)}</strong>
              </p>
            `
            : `
              <div class="campo">
                <label for="pm-categoria">
                  Categoría de gasto
                </label>

                <select
                  id="pm-categoria"
                  name="id_categoria"
                  required
                >
                  <option value="">
                    Selecciona una categoría…
                  </option>

                  ${opcionesHTML}
                </select>
              </div>
            `
        }

        ${campoMonto(
          editando ? presupuesto.monto_limite : ''
        )}

        ${
          !editando && !opciones.length
            ? `
              <p class="pm-error">
                No hay categorías disponibles
                para este período.
              </p>
            `
            : ''
        }
      `,
      editando
        ? 'Guardar cambios'
        : 'Crear presupuesto',
      `data-id="${id}" data-mes="${mes}" data-anio="${anio}"`
    );

    if (!editando && !opciones.length) {
      modal.querySelector(
        'button[type="submit"]'
      ).disabled = true;
    }
  }


  // ------------------------------------
  // MODAL CREAR/EDITAR META
  // ------------------------------------

  function modalMeta(
    tipo,
    meta = null
  ) {
    const editando = tipo === 'meta-editar';

    abrirModal(
      editando ? 'Editar meta' : 'Nueva meta',
      tipo,
      `
        <div class="campo">
          <label for="pm-meta-nombre">
            Nombre de la meta
          </label>

          <input
            id="pm-meta-nombre"
            name="nombre_meta"
            maxlength="80"
            value="${esc(meta?.nombre_meta || '')}"
            placeholder="Ej. Fondo de emergencias"
            required
          >
        </div>

        <div class="campo">
          <label for="pm-monto">
            Monto objetivo (COP)
          </label>

          <input
            id="pm-monto"
            name="monto"
            inputmode="decimal"
            value="${esc(meta?.monto_objetivo || '')}"
            placeholder="Ej. 2000000"
            required
          >
        </div>

        <div class="campo">
          <label for="pm-meta-fecha">
            Fecha objetivo
          </label>

          <input
            id="pm-meta-fecha"
            name="fecha_objetivo"
            type="date"
            value="${esc(
              meta?.fecha_objetivo ||
              fechaPorDefecto()
            )}"
            required
          >
        </div>

        <div class="campo">
          <label for="pm-meta-desc">
            Descripción (opcional)
          </label>

          <textarea
            id="pm-meta-desc"
            name="descripcion"
            maxlength="255"
            rows="3"
          >${esc(meta?.descripcion || '')}</textarea>
        </div>

        <p class="pm-modal-nota">
          ${
            editando
              ? (
                  'Puedes modificar el objetivo, ' +
                  'pero no reducirlo por debajo ' +
                  'del acumulado actual: ' +
                  cop(meta.monto_acumulado)
                )
              : (
                  'La meta comienza con $0. ' +
                  'Los aportes se registran después.'
                )
          }
        </p>
      `,
      editando ? 'Guardar cambios' : 'Crear meta',
      `data-id="${Number(meta?.id_meta || 0)}"`
    );
  }


  // ------------------------------------
  // MODAL REGISTRAR APORTE
  // ------------------------------------

  function modalAporte(meta) {
    const faltante = Math.max(
      0,
      numero(meta.monto_objetivo) -
      numero(meta.monto_acumulado)
    );

    abrirModal(
      'Registrar aporte',
      'meta-aportar',
      `
        <p class="pm-modal-nota">
          Meta: <strong>${esc(meta.nombre_meta)}</strong>

          <br>

          Acumulado actual:
          ${cop(meta.monto_acumulado)}

          <br>

          Pendiente:
          ${cop(faltante)}
        </p>

        ${campoMonto()}

        <p class="pm-nota">
          Este aporte aumenta el progreso
          declarado de la meta. No descuenta
          dinero de una cuenta bancaria.
        </p>
      `,
      'Registrar aporte',
      `data-id="${Number(meta.id_meta)}"
       data-acumulado="${esc(meta.monto_acumulado)}"
       data-faltante="${faltante}"`
    );
  }


  // ------------------------------------
  // CAMBIO DE PERÍODO
  // ------------------------------------

  selectorMes.value = String(mes);

  selectorMes.addEventListener('change', () => {
    mes = Number(selectorMes.value);
    pintarPresupuestos();
  });

  selectorAnio.addEventListener('change', () => {
    const valor = Number(selectorAnio.value);

    if (
      !Number.isInteger(valor) ||
      valor < 2000 ||
      valor > 9998
    ) {
      selectorAnio.value = String(anio);

      mensaje.textContent =
        'Selecciona un año entre 2000 y 9998.';
      return;
    }

    anio = valor;
    mensaje.textContent = '';
    pintarPresupuestos();
  });


  // ------------------------------------
  // NUEVO PRESUPUESTO
  // ------------------------------------

  nuevoPres.addEventListener('click', async () => {
    if (ocupada) return;

    mensaje.textContent = '';

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para crear presupuestos.';
      return;
    }

    ocupada = true;
    nuevoPres.disabled = true;

    try {
      const categorias = await obtenerCategorias();

      if (!Array.isArray(categorias)) {
        throw new Error(
          'No se pudieron consultar las categorías.'
        );
      }

      const existentes = new Set(
        presupuestos
          .filter(p =>
            Number(p.mes) === mes &&
            Number(p.anio) === anio
          )
          .map(p => Number(p.id_categoria))
      );

      const disponibles = categorias.filter(cat =>
        cat.estado === 'ACTIVA' &&
        cat.tipo_categoria === 'GASTO' &&
        !existentes.has(Number(cat.id_categoria))
      );

      modalPresupuesto(
        'pres-crear',
        disponibles
      );

    } catch (error) {
      mostrarError(error);

    } finally {
      ocupada = false;
      nuevoPres.disabled = false;
    }
  });


  // ------------------------------------
  // EDITAR PRESUPUESTO
  // ------------------------------------

  listaPres.addEventListener('click', event => {
    const boton = event.target.closest(
      'button[data-pres="editar"]'
    );

    if (!boton || ocupada) return;

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para editar.';
      return;
    }

    const presupuesto = presupuestoPorId(
      Number(boton.dataset.id)
    );

    if (presupuesto) {
      modalPresupuesto(
        'pres-editar',
        [],
        presupuesto
      );
    }
  });


  // ------------------------------------
  // NUEVA META
  // ------------------------------------

  nuevaMeta.addEventListener('click', () => {
    if (ocupada) return;

    mensaje.textContent = '';

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para crear metas.';
      return;
    }

    modalMeta('meta-crear');
  });


  // ------------------------------------
  // ACCIONES DE METAS
  // ------------------------------------

  listaMetas.addEventListener('click', async event => {
    const boton = event.target.closest(
      'button[data-meta]'
    );

    if (!boton || ocupada) return;

    const id = Number(boton.dataset.id);
    const accion = boton.dataset.meta;

    if (!metaPorId(id)) return;

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para administrar metas.';
      return;
    }

    if (accion === 'desactivar') {
      const confirmar = window.confirm(
        '¿Desactivar esta meta?\n\n' +
        'Solo puede desactivarse cuando ' +
        'no tiene aportes acumulados.'
      );

      if (!confirmar) return;

      ocupada = true;
      boton.disabled = true;

      try {
        await desactivarMeta(id);

        aviso(
          'Meta desactivada correctamente.',
          'ok'
        );

        await cargarTodo();

      } catch (error) {
        mostrarError(error);

      } finally {
        ocupada = false;

        if (boton.isConnected) {
          boton.disabled = false;
        }
      }

      return;
    }

    ocupada = true;
    boton.disabled = true;

    try {
      // Consultar la versión más reciente
      // antes de preparar una edición o aporte.
      const meta = await obtenerMeta(id);

      if (
        accion === 'editar' &&
        meta.estado !== 'INACTIVA'
      ) {
        modalMeta('meta-editar', meta);
      }

      if (
        accion === 'aportar' &&
        meta.estado === 'ACTIVA'
      ) {
        modalAporte(meta);
      }

    } catch (error) {
      mostrarError(error);

    } finally {
      ocupada = false;

      if (boton.isConnected) {
        boton.disabled = false;
      }
    }
  });


  // ------------------------------------
  // CERRAR VENTANA
  // ------------------------------------

  modal.addEventListener('click', event => {
    if (ocupada) return;

    if (
      event.target === modal ||
      event.target.closest('[data-cerrar]')
    ) {
      cerrarModal();
    }
  });

  modal.addEventListener('cancel', event => {
    if (ocupada) event.preventDefault();
  });


  // ------------------------------------
  // GUARDAR FORMULARIOS
  // ------------------------------------

  modal.addEventListener('submit', async event => {
    const form = event.target.closest('#pm-form');

    if (!form) return;

    event.preventDefault();

    if (ocupada) return;

    const error = form.querySelector(
      '#pm-modal-error'
    );

    error.textContent = '';

    if (!navigator.onLine) {
      error.textContent =
        'Necesitas conexión para guardar.';
      return;
    }

    const tipo = form.dataset.tipo;
    const id = Number(form.dataset.id || 0);

    const monto = form.elements.monto
      ? montoFormulario(form)
      : '';

    if (!montoValido(monto)) {
      error.textContent =
        'Escribe un monto válido mayor que cero, ' +
        'sin puntos de miles y con máximo dos decimales.';
      return;
    }

    let datos = {};

    if (tipo === 'pres-crear') {
      const idCategoria = Number(
        form.elements.id_categoria.value
      );

      if (
        !Number.isSafeInteger(idCategoria) ||
        idCategoria <= 0
      ) {
        error.textContent =
          'Selecciona una categoría de gasto.';
        return;
      }

      datos = {
        id_categoria: idCategoria,
        anio: Number(form.dataset.anio),
        mes: Number(form.dataset.mes),
        monto_limite: monto
      };
    }

    if (tipo === 'pres-editar') {
      datos = {
        monto_limite: monto
      };
    }

    if (
      tipo === 'meta-crear' ||
      tipo === 'meta-editar'
    ) {
      const nombre = form.elements.nombre_meta.value
        .trim()
        .replace(/\s+/g, ' ');

      const fecha =
        form.elements.fecha_objetivo.value;

      const descripcion =
        form.elements.descripcion.value.trim();

      if (!nombre || nombre.length > 80) {
        error.textContent =
          'Escribe un nombre válido.';
        return;
      }

      if (!fecha) {
        error.textContent =
          'Selecciona una fecha objetivo.';
        return;
      }

      if (tipo === 'meta-crear') {
        if (fecha < hoyISO()) {
          error.textContent =
            'La fecha objetivo no puede ser pasada.';
          return;
        }

        datos = {
          nombre_meta: nombre,
          monto_objetivo: monto,
          fecha_objetivo: fecha,
          descripcion: descripcion || null
        };

      } else {
        const original = metaPorId(id);

        if (!original) {
          error.textContent =
            'No se encontró la meta.';
          return;
        }

        if (
          Number(monto) <
          numero(original.monto_acumulado)
        ) {
          error.textContent =
            'El objetivo no puede ser menor ' +
            'que el acumulado.';
          return;
        }

        // Enviar solamente campos modificados.
        // Esto evita rechazar una edición de texto
        // cuando una fecha objetivo anterior venció.
        if (nombre !== original.nombre_meta) {
          datos.nombre_meta = nombre;
        }

        if (
          Number(monto) !==
          numero(original.monto_objetivo)
        ) {
          datos.monto_objetivo = monto;
        }

        if (fecha !== original.fecha_objetivo) {
          if (fecha < hoyISO()) {
            error.textContent =
              'La nueva fecha no puede ser pasada.';
            return;
          }

          datos.fecha_objetivo = fecha;
        }

        if (
          descripcion !==
          (original.descripcion || '')
        ) {
          datos.descripcion = descripcion || null;
        }

        if (!Object.keys(datos).length) {
          error.textContent =
            'No hay cambios para guardar.';
          return;
        }
      }
    }

    if (tipo === 'meta-aportar') {
      const faltante = numero(
        form.dataset.faltante
      );

      if (Number(monto) > faltante) {
        error.textContent =
          `El aporte supera lo pendiente: ${cop(faltante)}.`;
        return;
      }

      datos = {
        monto,
        acumulado_esperado:
          form.dataset.acumulado
      };
    }

    ocupada = true;

    const botones = [
      ...form.querySelectorAll('button')
    ];

    botones.forEach(b => {
      b.disabled = true;
    });

    let incierta = false;
    let guardada = false;

    try {
      if (tipo === 'pres-crear') {
        await crearPresupuesto(datos);

      } else if (tipo === 'pres-editar') {
        await actualizarPresupuesto(id, datos);

      } else if (tipo === 'meta-crear') {
        await crearMeta(datos);

      } else if (tipo === 'meta-editar') {
        await actualizarMeta(id, datos);

      } else if (tipo === 'meta-aportar') {
        await aportarMeta(id, datos);

      } else {
        throw new Error(
          'Operación no válida.'
        );
      }

      guardada = true;

      cerrarModal();

      aviso(
        tipo === 'meta-aportar'
          ? 'Progreso de la meta actualizado.'
          : 'Cambios guardados correctamente.',
        'ok'
      );

    } catch (errorSolicitud) {
      mostrarError(errorSolicitud, error);

      if (errorSolicitud instanceof ErrorDeRed) {
        incierta = true;
      }

    } finally {
      ocupada = false;

      botones.forEach(b => {
        if (b.isConnected) {
          b.disabled =
            incierta &&
            b.type === 'submit';
        }
      });
    }

    if (guardada) {
      try {
        await cargarTodo();

      } catch (errorRecarga) {
        mensaje.textContent =
          'La operación se guardó, pero no se ' +
          'pudo actualizar la pantalla. ' +
          'Recarga la vista cuando tengas conexión.';

        console.warn(errorRecarga);
      }
    }
  });


  // ------------------------------------
  // CARGA INICIAL
  // ------------------------------------

  try {
    await cargarTodo();

  } catch (error) {
    listaPres.innerHTML = errorCarga(error);
    listaMetas.innerHTML = errorCarga(error);
    mostrarError(error);
  }
}
