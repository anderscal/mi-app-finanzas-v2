
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
  desactivarMeta,
  obtenerSaldosReservados,
  obtenerDetalleReservasMeta,
  reservarDineroMeta,
  liberarDineroMeta,
  ErrorDeRed
} from '../api.js';

import { obtenerUsuario } from '../sesion.js';

import {
  cop,
  esc,
  nombreMes,
  hoyISO,
  nuevoUUID,
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

  const usuarioInicial = Number(
    obtenerUsuario()?.id_usuario
  );

  const mismaSesion = () =>
    Number.isSafeInteger(usuarioInicial) &&
    usuarioInicial > 0 &&
    Number(obtenerUsuario()?.id_usuario) === usuarioInicial;

  let presupuestos = [];

  let planificacion = {
    presupuestos: [],
    metas: []
  };

  let metas = [];
  let saldos = [];
  let detalles = new Map();

  let ocupada = false;
  let metaEditada = null;
  let intentoIncierto = null;
  let hayDatosGuardados = false;


  const num = valor =>
    Number.isFinite(Number(valor))
      ? Number(valor)
      : 0;

  const montoValido = valor =>
    /^(?:0|[1-9]\d{0,12})(?:\.\d{1,2})?$/.test(valor) &&
    Number(valor) > 0;

  const montoTexto = valor =>
    String(valor ?? '').trim().replace(',', '.');

  const periodo = () =>
    `${nombreMes(mes)} ${anio}`;

  const porcentaje = (parte, total) =>
    total > 0 ? 100 * parte / total : 0;

  const ancho = valor =>
    Math.min(100, Math.max(0, num(valor)));

  const errorTexto = e =>
    e instanceof ErrorDeRed
      ? (
          'No se recibió confirmación. ' +
          'Revisa los datos antes de crear ' +
          'una operación diferente.'
        )
      : (
          e?.message ||
          'No se pudo completar la operación.'
        );

  const metaId = id =>
    metas.find(
      m => Number(m.id_meta) === Number(id)
    );

  const presId = id =>
    presupuestos.find(
      p =>
        Number(p.id_presupuesto) === Number(id)
    );


  // ----------------------------------
  // ESTRUCTURA PRINCIPAL
  // ----------------------------------

  c.innerHTML = `
    <style>
      .pm-titulo {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        flex-wrap: wrap;
      }

      .pm-nuevo {
        border: 0;
        border-radius: 999px;
        background: #087a59;
        color: white;
        padding: 11px 15px;
        font: inherit;
        font-size: 13px;
        font-weight: 800;
      }

      .pm-nuevo:disabled,
      .pm-modal button:disabled {
        opacity: .5;
        cursor: not-allowed;
      }

      .pm-periodo {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 108px;
        gap: 10px;
        margin: 14px 0;
      }

      .pm-periodo label {
        display: flex;
        flex-direction: column;
        gap: 5px;
        font-size: 13px;
        font-weight: 700;
      }

      .pm-periodo input,
      .pm-periodo select {
        width: 100%;
        min-width: 0;
      }

      .pm-lista {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .pm-tarjeta {
        display: flex;
        flex-direction: column;
        gap: 10px;
        background: #f3f6f4;
        border-radius: 17px;
        padding: 16px;
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
        background: #e0f2e9;
        color: #08684c;
        padding: 5px 9px;
        font-size: 11px;
        font-weight: 800;
      }

      .pm-etiqueta.alerta {
        background: #fff0cd;
        color: #845400;
      }

      .pm-etiqueta.exceso {
        background: #ffe2da;
        color: #a13724;
      }

      .pm-nota {
        font-size: 12px;
        color: #586960;
        line-height: 1.5;
      }

      .pm-alerta {
        font-size: 12px;
        color: #915419;
        line-height: 1.5;
      }

      .pm-barra {
        height: 9px;
        background: #dbe6df;
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

      .pm-barra span.exceso {
        background: #bf5538;
      }

      .pm-acciones {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      .pm-resumen {
        display: grid;
        grid-template-columns:
          repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin: 12px 0;
      }

      .pm-resumen > div {
        background: #eef3ef;
        border-radius: 14px;
        padding: 13px;
        display: flex;
        flex-direction: column;
        gap: 5px;
        min-width: 0;
      }

      .pm-resumen span {
        font-size: 12px;
        color: #586960;
      }

      .pm-resumen strong {
        font-size: 17px;
        overflow-wrap: anywhere;
      }

      .pm-compacto {
        background: #e6f4ec;
        border-radius: 16px;
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 5px;
      }

      .pm-compacto .cantidad {
        font-weight: 800;
        font-size: 22px;
        color: #075640;
      }

      .pm-compacto .enlace {
        align-self: flex-start;
        padding: 4px 0;
      }

      .pm-error {
        color: #ad3021;
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
        background: white;
        color: #17251f;
        overflow: hidden;
        box-shadow: 0 18px 60px #0003;
      }

      .pm-modal[open] {
        display: flex;
        flex-direction: column;
      }

      .pm-modal::backdrop {
        background: #0009;
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
        border-bottom: 1px solid #e4ebe7;
      }

      .pm-modal-pie {
        border: 0;
        border-top: 1px solid #e4ebe7;
      }

      .pm-modal-pie button {
        flex: 1;
        min-width: 0;
      }

      .pm-modal-cabeza h2 {
        margin: 0;
        font-size: 20px;
      }

      .pm-cerrar {
        width: 36px;
        height: 36px;
        border: 0;
        border-radius: 50%;
        background: #edf1ef;
        font-size: 23px;
      }

      .pm-modal-cuerpo {
        min-height: 0;
        overflow-y: auto;
        overscroll-behavior: contain;
        padding: 20px;
      }

      .pm-modal-cuerpo .campo {
        margin-bottom: 15px;
      }

      .pm-modal-cuerpo input,
      .pm-modal-cuerpo select,
      .pm-modal-cuerpo textarea {
        width: 100%;
        max-width: 100%;
      }

      .pm-modal-cuerpo textarea {
        min-height: 75px;
      }

      .pm-modal-nota {
        background: #e4f3eb;
        color: #07533e;
        border-radius: 13px;
        padding: 12px;
        font-size: 13px;
        line-height: 1.5;
        margin-bottom: 14px;
      }

      .pm-condicional[hidden] {
        display: none;
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
      subtitulo:
        'Controla tus gastos y tus objetivos de ahorro'
    })}

    <section class="seccion">
      <div class="pm-titulo">
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
        <label>
          Mes

          <select id="pm-mes">
            ${
              Array.from(
                { length: 12 },
                (_, i) => `
                  <option value="${i + 1}">
                    ${nombreMes(i + 1)}
                  </option>
                `
              ).join('')
            }
          </select>
        </label>

        <label>
          Año

          <input
            id="pm-anio"
            type="number"
            min="2000"
            max="9998"
            value="${anio}"
          >
        </label>
      </div>

      <div
        id="pm-presupuestos"
        class="pm-lista"
      >
        ${cargando()}
      </div>
    </section>

    <section class="seccion">
      <div class="pm-titulo">
        <h2>Metas de ahorro</h2>

        <button
          type="button"
          class="pm-nuevo"
          id="pm-nueva-meta"
        >
          + Nueva meta
        </button>
      </div>

      <div
        id="pm-resumen-reservas"
        class="pm-compacto"
      >
        Consultando ahorro reservado…
      </div>

      <div
        id="pm-metas"
        class="pm-lista"
      >
        ${cargando()}
      </div>
    </section>

    <section class="seccion">
      <p
        id="pm-estado"
        class="nota"
        hidden
      ></p>

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


  // ----------------------------------
  // REFERENCIAS
  // ----------------------------------

  const $ = selector => c.querySelector(selector);

  const listaPres = $('#pm-presupuestos');
  const listaMetas = $('#pm-metas');
  const resumenReservas = $('#pm-resumen-reservas');

  const selectorMes = $('#pm-mes');
  const selectorAnio = $('#pm-anio');

  const botonPres = $('#pm-nuevo-pres');
  const botonMeta = $('#pm-nueva-meta');

  const modal = $('#pm-modal');
  const mensaje = $('#pm-error');
  const estado = $('#pm-estado');


  // ----------------------------------
  // CONSULTAS Y CACHÉ
  // ----------------------------------

  async function conCache(clave, consultar, validar) {
    try {
      const datos = await consultar();

      if (!mismaSesion()) {
        throw new Error(
          'La sesión cambió. Vuelve a abrir la pantalla.'
        );
      }

      if (!validar(datos)) {
        throw new Error(
          'Respuesta inválida: ' + clave
        );
      }

      guardarCache(clave, datos);

      return {
        datos,
        cache: false
      };

    } catch (e) {
      if (
        e instanceof ErrorDeRed &&
        mismaSesion()
      ) {
        const guardado = leerCache(clave);

        if (validar(guardado?.datos)) {
          return {
            datos: guardado.datos,
            cache: true
          };
        }
      }

      throw e;
    }
  }


  async function cargarTodo() {
    const [p, plan, m, s] = await Promise.all([
      conCache(
        'presupuestos',
        obtenerPresupuestos,
        Array.isArray
      ),

      conCache(
        'planificacion',
        obtenerPlanificacion,
        x =>
          Array.isArray(x?.presupuestos) &&
          Array.isArray(x?.metas)
      ),

      conCache(
        'metas',
        obtenerMetas,
        Array.isArray
      ),

      conCache(
        'metas-saldos-reservados',
        obtenerSaldosReservados,
        Array.isArray
      )
    ]);

    if (!mismaSesion()) return;

    presupuestos = p.datos;
    planificacion = plan.datos;
    metas = m.datos;
    saldos = s.datos;

    hayDatosGuardados =
      p.cache ||
      plan.cache ||
      m.cache ||
      s.cache;

    const resultados = await Promise.allSettled(
      metas.map(meta =>
        conCache(
          `meta-reservas-${meta.id_meta}`,
          () => obtenerDetalleReservasMeta(
            meta.id_meta
          ),
          x =>
            x &&
            Number(x.id_meta) === Number(meta.id_meta) &&
            Array.isArray(x.registros)
        )
      )
    );

    if (!mismaSesion()) return;

    detalles = new Map();

    resultados.forEach((resultado, i) => {
      if (resultado.status === 'fulfilled') {
        detalles.set(
          Number(metas[i].id_meta),
          resultado.value.datos
        );

        hayDatosGuardados ||= resultado.value.cache;
      }
    });

    estado.hidden = !hayDatosGuardados;

    estado.textContent = hayDatosGuardados
      ? (
          'Sin conexión: se muestran los últimos ' +
          'datos guardados. Las reservas requieren conexión.'
        )
      : '';

    pintarPresupuestos();
    pintarResumenReservas();
    pintarMetas();
  }


  // ----------------------------------
  // PRESUPUESTOS
  // ----------------------------------

  function pintarPresupuestos() {
    selectorMes.value = String(mes);
    selectorAnio.value = String(anio);

    const vigentes = presupuestos.filter(
      p =>
        Number(p.mes) === mes &&
        Number(p.anio) === anio
    );

    if (!vigentes.length) {
      listaPres.innerHTML = `
        <p class="vacio">
          No tienes presupuestos para
          ${esc(periodo())}.
        </p>
      `;

      return;
    }

    const calculos = new Map(
      planificacion.presupuestos.map(
        p => [Number(p.id_presupuesto), p]
      )
    );

    let limite = 0;
    let gastado = 0;
    let completos = true;

    const tarjetas = vigentes.map(p => {
      const calc = calculos.get(
        Number(p.id_presupuesto)
      );

      const total = num(p.monto_limite);
      limite += total;

      if (calc) {
        gastado += num(calc.gastado);
      } else {
        completos = false;
      }

      const pct = calc
        ? num(calc.porcentaje_usado)
        : null;

      const clase = pct === null
        ? ''
        : pct >= 100
          ? 'exceso'
          : pct >= 90
            ? 'alerta'
            : '';

      const disponible = calc
        ? num(calc.disponible)
        : null;

      return `
        <article class="pm-tarjeta">
          <div class="pm-fila">
            <strong>
              ${
                esc(
                  calc?.categoria ||
                  'Categoría #' + p.id_categoria
                )
              }
            </strong>

            <span class="pm-etiqueta ${clase}">
              ${
                pct === null
                  ? 'Sin cálculo'
                  : pct >= 100
                    ? 'Límite alcanzado'
                    : pct >= 90
                      ? 'Cerca del límite'
                      : 'En presupuesto'
              }
            </span>
          </div>

          <div class="pm-fila">
            <strong class="monto">
              ${
                calc
                  ? cop(calc.gastado)
                  : '—'
              }
            </strong>

            <span class="pm-nota">
              de ${cop(total)}
            </span>
          </div>

          <div
            class="pm-barra"
            role="img"
            aria-label="${
              pct === null
                ? 'Porcentaje no disponible'
                : pct.toFixed(1) + '% utilizado'
            }"
          >
            <span
              class="${clase}"
              style="width:${ancho(pct)}%"
            ></span>
          </div>

          <div class="pm-fila">
            <span class="pm-nota">
              ${
                disponible === null
                  ? 'Sin cálculo'
                  : disponible >= 0
                    ? 'Disponible ' + cop(disponible)
                    : 'Excedido en ' + cop(-disponible)
              }

              ${
                pct === null
                  ? ''
                  : ' · ' + pct.toFixed(1) + '%'
              }
            </span>

            <button
              type="button"
              class="btn btn-chico"
              data-pres="editar"
              data-id="${
                Number(p.id_presupuesto)
              }"
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
            ${cop(limite)}
          </strong>
        </div>

        <div>
          <span>Gastado del período</span>

          <strong class="monto">
            ${
              completos
                ? cop(gastado)
                : 'Pendiente'
            }
          </strong>
        </div>
      </div>

      ${tarjetas}
    `;
  }


  // ----------------------------------
  // RESUMEN COMPACTO DE RESERVAS
  // ----------------------------------

  function pintarResumenReservas() {
    const reservado = saldos.reduce(
      (total, s) =>
        total + num(s.monto_reservado),
      0
    );

    const cuentasConReserva = saldos.filter(
      s => num(s.monto_reservado) > 0
    ).length;

    resumenReservas.innerHTML = `
      <span class="pm-nota">
        Dinero reservado para tus metas
      </span>

      <span class="cantidad monto">
        ${cop(reservado)}
      </span>

      <span class="pm-nota">
        ${cuentasConReserva} cuenta(s) con reservas

        ${
          hayDatosGuardados
            ? ' · datos guardados'
            : ''
        }
      </span>

      <a
        class="enlace"
        href="#/inicio"
      >
        Ver saldo libre y detalle por cuenta en Inicio
      </a>
    `;
  }


  // ----------------------------------
  // METAS DE AHORRO
  // ----------------------------------

  function pintarMetas() {
    if (!metas.length) {
      listaMetas.innerHTML = `
        <p class="vacio">
          Aún no tienes metas.
          Usa «Nueva meta» para comenzar.
        </p>
      `;

      return;
    }

    listaMetas.innerHTML = metas.map(meta => {
      const id = Number(meta.id_meta);
      const acumulado = num(meta.monto_acumulado);
      const objetivo = num(meta.monto_objetivo);
      const pct = porcentaje(acumulado, objetivo);

      const detalle = detalles.get(id);

      const vinculado = detalle
        ? num(detalle.monto_vinculado)
        : null;

      const anterior = detalle
        ? num(detalle.monto_sin_vincular)
        : null;

      const activa = meta.estado === 'ACTIVA';

      return `
        <article class="pm-tarjeta">
          <div class="pm-fila">
            <strong>
              ${esc(meta.nombre_meta)}
            </strong>

            <span class="pm-etiqueta">
              ${
                meta.estado === 'CUMPLIDA'
                  ? 'Cumplida'
                  : meta.estado === 'INACTIVA'
                    ? 'Inactiva'
                    : 'En progreso'
              }
            </span>
          </div>

          <div class="pm-fila">
            <strong class="monto">
              ${cop(acumulado)}
            </strong>

            <span class="pm-nota">
              de ${cop(objetivo)}
              · ${pct.toFixed(1)}%
            </span>
          </div>

          <div
            class="pm-barra"
            role="img"
            aria-label="${pct.toFixed(1)}% de la meta"
          >
            <span
              style="width:${ancho(pct)}%"
            ></span>
          </div>

          <p class="pm-nota">
            Reservado en cuentas:
            <strong class="monto">
              ${
                vinculado === null
                  ? 'Sin verificar'
                  : cop(vinculado)
              }
            </strong>

            · Aportes antiguos sin vincular:

            <strong class="monto">
              ${
                anterior === null
                  ? 'Sin verificar'
                  : cop(anterior)
              }
            </strong>
          </p>

          ${
            anterior > 0
              ? `
                <p class="pm-alerta">
                  Tienes ahorro declarado anteriormente
                  que todavía no está respaldado
                  por una cuenta.
                </p>
              `
              : ''
          }

          <p class="pm-nota">
            Faltan
            <span class="monto">
              ${
                cop(
                  Math.max(
                    0,
                    objetivo - acumulado
                  )
                )
              }
            </span>

            · Objetivo ${esc(meta.fecha_objetivo)}
          </p>

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
            meta.estado === 'INACTIVA'
              ? ''
              : `
                <div class="pm-acciones">
                  ${
                    activa
                      ? `
                        <button
                          type="button"
                          class="btn btn-primario btn-chico"
                          data-meta="reservar"
                          data-id="${id}"
                        >
                          Reservar dinero
                        </button>
                      `
                      : ''
                  }

                  ${
                    vinculado > 0
                      ? `
                        <button
                          type="button"
                          class="btn btn-chico"
                          data-meta="liberar"
                          data-id="${id}"
                        >
                          Liberar ahorro
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
          }
        </article>
      `;
    }).join('');
  }


  // ----------------------------------
  // MODAL COMPARTIDO
  // ----------------------------------

  function abrirModal(
    titulo,
    tipo,
    contenido,
    textoBoton,
    atributos = ''
  ) {
    intentoIncierto = null;

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
            ${esc(textoBoton)}
          </button>
        </div>
      </form>
    `;

    if (modal.open) {
      modal.close();
    }

    modal.showModal();
  }


  function campoMonto(
    nombre,
    valor = '',
    titulo = 'Monto (COP)'
  ) {
    return `
      <div class="campo">
        <label for="pm-monto">
          ${esc(titulo)}
        </label>

        <input
          id="pm-monto"
          name="${nombre}"
          inputmode="decimal"
          autocomplete="off"
          value="${esc(valor)}"
          placeholder="Ej. 100000"
          required
        >

        <small class="ayuda">
          Sin separadores de miles,
          máximo dos decimales.
        </small>
      </div>
    `;
  }


  function opcionesCuentas(cuentas, limites) {
    return `
      <option value="">
        Selecciona una cuenta…
      </option>

      ${
        cuentas.map(s => {
          const max = num(
            limites.get(Number(s.id_cuenta)) || 0
          );

          return `
            <option
              value="${Number(s.id_cuenta)}"
              data-max="${max}"
            >
              ${esc(s.nombre_cuenta)}
              · ${cop(max)} disponibles
            </option>
          `;
        }).join('')
      }
    `;
  }


  // ----------------------------------
  // FORMULARIO PRESUPUESTOS
  // ----------------------------------

  function formularioPresupuesto(
    tipo,
    opciones = [],
    p = null
  ) {
    const editar = tipo === 'pres-editar';

    const id = Number(
      p?.id_presupuesto || 0
    );

    const calc = planificacion.presupuestos.find(
      x => Number(x.id_presupuesto) === id
    );

    abrirModal(
      editar
        ? 'Editar presupuesto'
        : 'Nuevo presupuesto',
      tipo,
      `
        <p class="pm-modal-nota">
          Período: ${esc(periodo())}.
          Cambiar el límite no mueve dinero.
        </p>

        ${
          editar
            ? `
              <p class="pm-nota">
                Categoría:
                ${
                  esc(
                    calc?.categoria ||
                    'Categoría #' + p.id_categoria
                  )
                }
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

                  ${
                    opciones.map(x => `
                      <option value="${
                        Number(x.id_categoria)
                      }">
                        ${esc(x.nombre_categoria)}
                      </option>
                    `).join('')
                  }
                </select>
              </div>
            `
        }

        ${
          campoMonto(
            'monto_limite',
            editar ? p.monto_limite : '',
            'Límite mensual (COP)'
          )
        }

        ${
          !editar && !opciones.length
            ? `
              <p class="pm-error">
                No hay categorías disponibles
                para este período.
              </p>
            `
            : ''
        }
      `,
      editar
        ? 'Guardar cambios'
        : 'Crear presupuesto',
      `
        data-id="${id}"
        data-anio="${anio}"
        data-mes="${mes}"
      `
    );

    if (!editar && !opciones.length) {
      modal.querySelector(
        'button[type="submit"]'
      ).disabled = true;
    }
  }


  function fechaDefecto() {
    const fecha = new Date();

    fecha.setDate(
      fecha.getDate() + 90
    );

    const dos = x =>
      String(x).padStart(2, '0');

    return (
      `${fecha.getFullYear()}-` +
      `${dos(fecha.getMonth() + 1)}-` +
      `${dos(fecha.getDate())}`
    );
  }


  // ----------------------------------
  // FORMULARIO METAS
  // ----------------------------------

  function formularioMeta(tipo, meta = null) {
    const editar = tipo === 'meta-editar';

    metaEditada = editar ? meta : null;

    const limites = new Map(
      saldos
        .filter(s => s.estado === 'ACTIVA')
        .map(s => [
          Number(s.id_cuenta),
          Math.max(
            0,
            num(s.saldo_libre)
          )
        ])
    );

    abrirModal(
      editar ? 'Editar meta' : 'Nueva meta',
      tipo,
      `
        <div class="campo">
          <label for="pm-nombre-meta">
            Nombre de la meta
          </label>

          <input
            id="pm-nombre-meta"
            name="nombre_meta"
            maxlength="80"
            value="${
              esc(meta?.nombre_meta || '')
            }"
            placeholder="Ej. Comprar computador"
            required
          >
        </div>

        ${
          campoMonto(
            'monto_objetivo',
            meta?.monto_objetivo || '',
            'Monto objetivo (COP)'
          )
        }

        <div class="campo">
          <label for="pm-fecha">
            Fecha objetivo
          </label>

          <input
            id="pm-fecha"
            name="fecha_objetivo"
            type="date"
            value="${
              esc(
                meta?.fecha_objetivo ||
                fechaDefecto()
              )
            }"
            required
          >
        </div>

        <div class="campo">
          <label for="pm-descripcion">
            Descripción (opcional)
          </label>

          <textarea
            id="pm-descripcion"
            name="descripcion"
            maxlength="255"
            rows="3"
          >${esc(meta?.descripcion || '')}</textarea>
        </div>

        ${
          editar
            ? `
              <p class="pm-modal-nota">
                Acumulado actual:
                ${cop(meta.monto_acumulado)}.

                El objetivo no puede ser menor.
              </p>
            `
            : `
              <div class="campo">
                <label for="pm-reserva-ahora">
                  ¿Reservar dinero ahora? *
                </label>

                <select
                  id="pm-reserva-ahora"
                  name="reserva_ahora"
                  required
                >
                  <option value="">
                    Selecciona una opción…
                  </option>

                  <option value="si">
                    Sí, reservar desde una cuenta
                  </option>

                  <option value="no">
                    No, reservaré después
                  </option>
                </select>
              </div>

              <div
                id="pm-reserva-inicial"
                class="pm-condicional"
                hidden
              >
                <div class="campo">
                  <label for="pm-cuenta">
                    Cuenta financiera
                  </label>

                  <select
                    id="pm-cuenta"
                    name="id_cuenta"
                  >
                    ${
                      opcionesCuentas(
                        saldos.filter(
                          s => s.estado === 'ACTIVA'
                        ),
                        limites
                      )
                    }
                  </select>
                </div>

                ${
                  campoMonto(
                    'monto_reserva',
                    '',
                    'Cantidad para reservar (COP)'
                  )
                }

                <p class="pm-nota">
                  La creación y la reserva son
                  solicitudes separadas. Si la
                  reserva falla, la meta continuará
                  creada.
                </p>
              </div>

              <p class="pm-modal-nota">
                Reservar no cambia el saldo real;
                reduce el saldo libre.
              </p>
            `
        }
      `,
      editar
        ? 'Guardar cambios'
        : 'Crear meta',
      `
        data-id="${
          Number(meta?.id_meta || 0)
        }"

        data-uuid="${
          editar ? '' : nuevoUUID()
        }"
      `
    );

    if (!editar) {
      modal.querySelector(
        'button[type="submit"]'
      ).disabled = true;
    }
  }


  // ----------------------------------
  // RESERVAS POR CUENTA
  // ----------------------------------

  function porCuenta(detalle) {
    const map = new Map();

    for (const evento of detalle.registros) {
      if (evento.estado !== 'ACTIVO') {
        continue;
      }

      const id = Number(evento.id_cuenta);
      const previo = map.get(id) || 0;

      map.set(
        id,
        previo + (
          evento.tipo === 'RESERVA'
            ? num(evento.monto)
            : -num(evento.monto)
        )
      );
    }

    return map;
  }


  function formularioReserva(
    tipo,
    meta,
    detalle,
    cuentas
  ) {
    const liberar = tipo === 'meta-liberar';

    const faltante = Math.max(
      0,
      num(meta.monto_objetivo) -
      num(meta.monto_acumulado)
    );

    const limites = liberar
      ? porCuenta(detalle)
      : new Map(
          cuentas.map(x => [
            Number(x.id_cuenta),
            Math.max(
              0,
              num(x.saldo_libre)
            )
          ])
        );

    const candidatas = cuentas.filter(
      s =>
        s.estado === 'ACTIVA' &&
        num(
          limites.get(Number(s.id_cuenta))
        ) > 0
    );

    abrirModal(
      liberar
        ? 'Liberar ahorro'
        : 'Reservar para la meta',
      tipo,
      `
        <p class="pm-modal-nota">
          <strong>
            ${esc(meta.nombre_meta)}
          </strong>

          <br>

          Acumulado:
          ${cop(meta.monto_acumulado)}
          de ${cop(meta.monto_objetivo)}

          <br>

          ${
            liberar
              ? (
                  'Libera únicamente dinero ' +
                  'reservado en la cuenta elegida.'
                )
              : (
                  'Pendiente del objetivo: ' +
                  cop(faltante)
                )
          }
        </p>

        <div class="campo">
          <label for="pm-cuenta">
            Cuenta ${
              liberar
                ? 'de la reserva'
                : 'desde la que reservarás'
            }
          </label>

          <select
            id="pm-cuenta"
            name="id_cuenta"
            required
          >
            ${
              opcionesCuentas(
                candidatas,
                limites
              )
            }
          </select>
        </div>

        ${campoMonto('monto')}

        <p class="pm-nota">
          Esta operación cambia el dinero libre
          y el avance de la meta, no el saldo
          bancario real.
        </p>

        ${
          !candidatas.length
            ? `
              <p class="pm-error">
                No hay cuentas disponibles
                para esta operación.
              </p>
            `
            : ''
        }
      `,
      liberar
        ? 'Liberar ahorro'
        : 'Confirmar reserva',
      `
        data-id="${
          Number(meta.id_meta)
        }"

        data-uuid="${
          nuevoUUID()
        }"

        data-max-meta="${faltante}"
      `
    );

    if (!candidatas.length) {
      modal.querySelector(
        'button[type="submit"]'
      ).disabled = true;
    }
  }


  async function prepararReserva(id, tipo) {
    const [meta, detalle, cuentas] =
      await Promise.all([
        obtenerMeta(id),
        obtenerDetalleReservasMeta(id),
        obtenerSaldosReservados()
      ]);

    if (!mismaSesion()) return;

    if (
      meta.estado === 'INACTIVA' ||
      (
        tipo === 'meta-reservar' &&
        meta.estado !== 'ACTIVA'
      )
    ) {
      throw new Error(
        'Esta meta no admite esa operación.'
      );
    }

    formularioReserva(
      tipo,
      meta,
      detalle,
      cuentas
    );
  }


  // ----------------------------------
  // CAMBIO DE PERÍODO
  // ----------------------------------

  selectorMes.value = String(mes);

  selectorMes.addEventListener('change', () => {
    mes = Number(selectorMes.value);
    pintarPresupuestos();
  });

  selectorAnio.addEventListener('change', () => {
    const nuevo = Number(selectorAnio.value);

    if (
      !Number.isInteger(nuevo) ||
      nuevo < 2000 ||
      nuevo > 9998
    ) {
      selectorAnio.value = String(anio);

      mensaje.textContent =
        'Selecciona un año válido ' +
        'entre 2000 y 9998.';

      return;
    }

    anio = nuevo;
    mensaje.textContent = '';

    pintarPresupuestos();
  });


  // ----------------------------------
  // NUEVO PRESUPUESTO
  // ----------------------------------

  botonPres.addEventListener('click', async () => {
    if (ocupada) return;

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para crear presupuestos.';
      return;
    }

    ocupada = true;
    botonPres.disabled = true;
    mensaje.textContent = '';

    try {
      const cats = await obtenerCategorias();

      if (!Array.isArray(cats)) {
        throw new Error(
          'No se pudieron obtener categorías.'
        );
      }

      if (!mismaSesion()) return;

      const usadas = new Set(
        presupuestos
          .filter(
            p =>
              Number(p.mes) === mes &&
              Number(p.anio) === anio
          )
          .map(p => Number(p.id_categoria))
      );

      formularioPresupuesto(
        'pres-crear',
        cats.filter(
          x =>
            x.estado === 'ACTIVA' &&
            x.tipo_categoria === 'GASTO' &&
            !usadas.has(
              Number(x.id_categoria)
            )
        )
      );

    } catch (e) {
      mensaje.textContent = errorTexto(e);

    } finally {
      ocupada = false;
      botonPres.disabled = false;
    }
  });


  listaPres.addEventListener('click', e => {
    const btn = e.target.closest(
      'button[data-pres="editar"]'
    );

    if (!btn || ocupada) return;

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para editar.';
      return;
    }

    const pres = presId(
      Number(btn.dataset.id)
    );

    if (pres) {
      formularioPresupuesto(
        'pres-editar',
        [],
        pres
      );
    }
  });


  // ----------------------------------
  // NUEVA META
  // ----------------------------------

  botonMeta.addEventListener('click', async () => {
    if (ocupada) return;

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para crear metas.';
      return;
    }

    ocupada = true;
    botonMeta.disabled = true;
    mensaje.textContent = '';

    try {
      const respuesta =
        await obtenerSaldosReservados();

      if (!mismaSesion()) return;

      saldos = respuesta;
      formularioMeta('meta-crear');

    } catch (e) {
      mensaje.textContent = errorTexto(e);

    } finally {
      ocupada = false;
      botonMeta.disabled = false;
    }
  });


  // ----------------------------------
  // ACCIONES SOBRE METAS
  // ----------------------------------

  listaMetas.addEventListener('click', async e => {
    const btn = e.target.closest(
      'button[data-meta]'
    );

    if (!btn || ocupada) return;

    const id = Number(btn.dataset.id);
    const accion = btn.dataset.meta;

    if (!metaId(id)) return;

    if (!navigator.onLine) {
      mensaje.textContent =
        'Necesitas conexión para administrar metas.';
      return;
    }

    if (accion === 'desactivar') {
      if (!window.confirm(
        '¿Desactivar esta meta sin ahorro acumulado?'
      )) {
        return;
      }

      ocupada = true;
      btn.disabled = true;

      try {
        await desactivarMeta(id);

        aviso(
          'Meta desactivada.',
          'ok'
        );

        await cargarTodo();

      } catch (err) {
        mensaje.textContent = errorTexto(err);

      } finally {
        ocupada = false;

        if (btn.isConnected) {
          btn.disabled = false;
        }
      }

      return;
    }

    ocupada = true;
    btn.disabled = true;
    mensaje.textContent = '';

    try {
      if (accion === 'editar') {
        const meta = await obtenerMeta(id);

        if (!mismaSesion()) return;

        if (meta.estado === 'INACTIVA') {
          throw new Error(
            'La meta está inactiva.'
          );
        }

        formularioMeta(
          'meta-editar',
          meta
        );

      } else if (
        accion === 'reservar' ||
        accion === 'liberar'
      ) {
        await prepararReserva(
          id,
          `meta-${accion}`
        );
      }

    } catch (err) {
      mensaje.textContent = errorTexto(err);

    } finally {
      ocupada = false;

      if (btn.isConnected) {
        btn.disabled = false;
      }
    }
  });


  // ----------------------------------
  // DECISIÓN RESERVA INICIAL
  // ----------------------------------

  modal.addEventListener('change', e => {
    if (
      e.target.id !== 'pm-reserva-ahora'
    ) {
      return;
    }

    const form = modal.querySelector('#pm-form');

    if (
      !form ||
      form.dataset.tipo !== 'meta-crear'
    ) {
      return;
    }

    const si = e.target.value === 'si';
    const no = e.target.value === 'no';

    form.querySelector(
      '#pm-reserva-inicial'
    ).hidden = !si;

    form.querySelector(
      'button[type="submit"]'
    ).disabled = !(si || no);
  });


  // ----------------------------------
  // CERRAR FORMULARIOS
  // ----------------------------------

  modal.addEventListener('click', e => {
    if (ocupada) return;

    if (
      e.target === modal ||
      e.target.closest('[data-cerrar]')
    ) {
      if (
        intentoIncierto &&
        !window.confirm(
          'Hay una operación sin confirmar. ' +
          '¿Cerrar y comprobarla después?'
        )
      ) {
        return;
      }

      intentoIncierto = null;

      if (modal.open) {
        modal.close();
      }
    }
  });

  modal.addEventListener('cancel', e => {
    if (
      ocupada ||
      (
        intentoIncierto &&
        !window.confirm(
          'Hay una operación sin confirmar. ' +
          '¿Cerrar y comprobarla después?'
        )
      )
    ) {
      e.preventDefault();
    }
  });


  // ----------------------------------
  // GUARDAR FORMULARIOS
  // ----------------------------------

  modal.addEventListener('submit', async e => {
    const form = e.target.closest('#pm-form');

    if (!form) return;

    e.preventDefault();

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

    let tipo = form.dataset.tipo;
    let id = Number(form.dataset.id || 0);
    let datos = {};

    const reintento =
      intentoIncierto &&
      intentoIncierto.form === form;

    if (reintento) {
      ({
        tipo,
        id,
        datos
      } = intentoIncierto);

    } else {
      const controlMonto =
        form.elements.monto ||
        form.elements.monto_limite ||
        form.elements.monto_objetivo;

      const monto = montoTexto(
        controlMonto?.value
      );

      if (!montoValido(monto)) {
        error.textContent =
          'Monto mayor que cero, sin separadores ' +
          'de miles y máximo dos decimales.';

        return;
      }

      if (tipo === 'pres-crear') {
        const cat = Number(
          form.elements.id_categoria.value
        );

        if (
          !Number.isSafeInteger(cat) ||
          cat <= 0
        ) {
          error.textContent =
            'Selecciona una categoría.';
          return;
        }

        datos = {
          id_categoria: cat,
          anio: Number(form.dataset.anio),
          mes: Number(form.dataset.mes),
          monto_limite: monto
        };

      } else if (tipo === 'pres-editar') {
        datos = {
          monto_limite: monto
        };

      } else if (
        tipo === 'meta-crear' ||
        tipo === 'meta-editar'
      ) {
        const nombre = form.elements.nombre_meta.value
          .trim()
          .replace(/\s+/g, ' ');

        const fecha =
          form.elements.fecha_objetivo.value;

        const desc =
          form.elements.descripcion.value.trim();

        if (
          !nombre ||
          nombre.length > 80 ||
          !fecha
        ) {
          error.textContent =
            'Completa el nombre y la fecha.';
          return;
        }

        if (tipo === 'meta-crear') {
          if (fecha < hoyISO()) {
            error.textContent =
              'La fecha objetivo no puede ser pasada.';
            return;
          }

          const eleccion =
            form.elements.reserva_ahora.value;

          if (
            !['si', 'no'].includes(eleccion)
          ) {
            error.textContent =
              'Debes decidir si reservarás dinero ahora.';
            return;
          }

          if (eleccion === 'si') {
            const cuenta = Number(
              form.elements.id_cuenta.value
            );

            const cantidad = montoTexto(
              form.elements.monto_reserva.value
            );

            const max = num(
              form.elements.id_cuenta
                .selectedOptions[0]?.dataset.max
            );

            if (
              !Number.isSafeInteger(cuenta) ||
              cuenta <= 0 ||
              !montoValido(cantidad) ||
              Number(cantidad) > max ||
              Number(cantidad) > Number(monto)
            ) {
              error.textContent =
                'Selecciona cuenta y reserva válidas, ' +
                'sin superar el saldo libre ni el objetivo.';

              return;
            }

            datos._reserva = {
              uuid_operacion: form.dataset.uuid,
              id_cuenta: cuenta,
              monto: cantidad,
              fecha_operacion: hoyISO()
            };
          }

          Object.assign(datos, {
            nombre_meta: nombre,
            monto_objetivo: monto,
            fecha_objetivo: fecha,
            descripcion: desc || null
          });

        } else {
          const original =
            Number(metaEditada?.id_meta) === id
              ? metaEditada
              : metaId(id);

          if (!original) {
            error.textContent =
              'Meta no encontrada.';
            return;
          }

          if (
            Number(monto) <
            num(original.monto_acumulado)
          ) {
            error.textContent =
              'El objetivo no puede ser menor al acumulado.';

            return;
          }

          if (nombre !== original.nombre_meta) {
            datos.nombre_meta = nombre;
          }

          if (
            Number(monto) !==
            num(original.monto_objetivo)
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
            desc !==
            (original.descripcion || '')
          ) {
            datos.descripcion = desc || null;
          }

          if (!Object.keys(datos).length) {
            error.textContent =
              'No hay cambios para guardar.';
            return;
          }
        }

      } else if (
        tipo === 'meta-reservar' ||
        tipo === 'meta-liberar'
      ) {
        const cuenta = Number(
          form.elements.id_cuenta.value
        );

        const max = num(
          form.elements.id_cuenta
            .selectedOptions[0]?.dataset.max
        );

        if (
          !Number.isSafeInteger(cuenta) ||
          cuenta <= 0 ||
          Number(monto) > max ||
          (
            tipo === 'meta-reservar' &&
            Number(monto) >
            num(form.dataset.maxMeta)
          )
        ) {
          error.textContent =
            'El monto supera el saldo disponible ' +
            'o no has seleccionado cuenta.';

          return;
        }

        datos = {
          uuid_operacion: form.dataset.uuid,
          id_cuenta: cuenta,
          monto,
          fecha_operacion: hoyISO()
        };

      } else {
        error.textContent =
          'Operación no reconocida.';

        return;
      }
    }

    ocupada = true;

    const botones = [
      ...form.querySelectorAll('button')
    ];

    botones.forEach(
      b => b.disabled = true
    );

    let confirmada = false;
    let parcial = false;
    let incierta = false;

    try {
      if (tipo === 'pres-crear') {
        await crearPresupuesto(datos);

      } else if (tipo === 'pres-editar') {
        await actualizarPresupuesto(
          id,
          datos
        );

      } else if (tipo === 'meta-crear') {
        const {
          _reserva: reserva,
          ...metaDatos
        } = datos;

        const creada = await crearMeta(
          metaDatos
        );

        if (reserva) {
          try {
            await reservarDineroMeta(
              creada.id_meta,
              reserva
            );

          } catch (err) {
            parcial = true;

            mensaje.textContent =
              err instanceof ErrorDeRed
                ? (
                    'Meta creada; no se confirmó ' +
                    'la reserva. Comprueba su detalle ' +
                    'antes de repetirla.'
                  )
                : (
                    'Meta creada sin reserva inicial: ' +
                    errorTexto(err) +
                    '. Puedes reservar después.'
                  );
          }
        }

      } else if (tipo === 'meta-editar') {
        await actualizarMeta(
          id,
          datos
        );

      } else if (tipo === 'meta-reservar') {
        await reservarDineroMeta(
          id,
          datos
        );

      } else if (tipo === 'meta-liberar') {
        await liberarDineroMeta(
          id,
          datos
        );
      }

      confirmada = true;

    } catch (err) {
      error.textContent = errorTexto(err);

      if (err instanceof ErrorDeRed) {
        incierta = true;
      }

    } finally {
      ocupada = false;

      botones.forEach(b => {
        if (b.isConnected) {
          b.disabled = false;
        }
      });
    }

    if (confirmada) {
      intentoIncierto = null;

      if (modal.open) {
        modal.close();
      }

      if (!parcial) {
        aviso(
          'Operación guardada correctamente.',
          'ok'
        );
      }

      try {
        await cargarTodo();

      } catch {
        mensaje.textContent =
          'Se guardó, pero no se pudo actualizar ' +
          'la pantalla. Recarga al tener conexión.';
      }

    } else if (incierta) {
      if (
        tipo === 'meta-reservar' ||
        tipo === 'meta-liberar'
      ) {
        intentoIncierto = {
          form,
          tipo,
          id,
          datos
        };

        form.querySelectorAll(
          'input,select,textarea'
        ).forEach(
          el => el.disabled = true
        );

        const submit = form.querySelector(
          'button[type="submit"]'
        );

        submit.textContent =
          'Reintentar misma operación';

        submit.disabled = false;

        error.textContent =
          'Respuesta incierta: puedes reintentar ' +
          'exactamente la misma operación ' +
          'con el mismo UUID.';

      } else {
        form.querySelector(
          'button[type="submit"]'
        ).disabled = true;

        error.textContent =
          'Sin confirmación. Consulta las metas ' +
          'o presupuestos antes de crear otra operación.';
      }
    }
  });


  // ----------------------------------
  // CARGA INICIAL
  // ----------------------------------

  try {
    await cargarTodo();

  } catch (e) {
    listaPres.innerHTML = errorCarga(e);

    resumenReservas.textContent =
      'No se pudo verificar el total reservado.';

    listaMetas.innerHTML = errorCarga(e);

    mensaje.textContent = errorTexto(e);
  }
}
