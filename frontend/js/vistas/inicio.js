import {
  obtenerMisCuentas,
  obtenerResumenMensual,
  obtenerHistorialMensual,
  ErrorDeRed
} from '../api.js';

import {
  obtenerUsuario,
  cerrarSesion
} from '../sesion.js';

import {
  operacionesLocales
} from '../offline.js';

import {
  cop,
  esc,
  icono,
  fechaCorta,
  nombreMes,
  guardarCache,
  leerCache
} from '../util.js';

import {
  cargando,
  errorCarga
} from './comun.js';

import {
  consultarReservasVisibles,
  encontrarSaldoReserva
} from '../saldo-consulta.js';


const NOMBRES_TIPO = {
  AHORROS: 'Ahorros',
  CORRIENTE: 'Corriente',
  EFECTIVO: 'Efectivo'
};


function saldosOcultos() {
  try {
    return localStorage.getItem('fp:ocultar') === '1';
  } catch {
    return false;
  }
}


export async function render(c) {
  const usuario = obtenerUsuario() || {};

  const iniciales = (
    (usuario.nombre_1 || '?')[0] +
    (usuario.apellido_1 || '')[0]
  ).toUpperCase();

  const hoy = new Date();
  const anio = hoy.getFullYear();
  const mes = hoy.getMonth() + 1;

  c.innerHTML = `
    <style>
      /* Carrusel horizontal de cuentas */

      .inicio-carrusel-cuentas {
        display: grid;
        grid-auto-flow: column;

        grid-auto-columns:
          minmax(
            148px,
            calc((100% - 20px) / 3)
          );

        gap: 10px;
        width: 100%;
        min-width: 0;

        overflow-x: auto;
        overflow-y: hidden;

        scroll-snap-type: x proximity;
        overscroll-behavior-inline: contain;
        -webkit-overflow-scrolling: touch;

        padding: 3px 0 12px;

        scrollbar-width: thin;
      }

      .inicio-mini-cuenta {
        display: flex;
        flex-direction: column;
        gap: 9px;

        box-sizing: border-box;
        width: 100%;
        min-width: 0;
        height: 100%;

        padding: 12px;
        border-radius: 16px;

        background: var(--c-bg-f2f5f3);
        border: 1px solid var(--c-bd-e1e9e4);

        scroll-snap-align: start;
      }

      .inicio-mini-cuenta.inactiva {
        opacity: .7;
      }

      .inicio-mini-icono {
        display: flex;
        align-items: center;
        justify-content: center;

        width: 35px;
        height: 35px;

        border-radius: 50%;
        background: var(--c-bg-ffffff);
        color: var(--c-tx-087a59);

        font-size: 17px;
        font-weight: 900;
        flex-shrink: 0;
      }

      .inicio-mini-identidad {
        display: flex;
        flex-direction: column;
        gap: 4px;
        flex: 1;

        min-width: 0;
      }

      .inicio-mini-nombre {
        display: block;
        margin: 0;

        color: var(--c-tx-142b21);
        font-size: 13px;
        font-weight: 800;
        line-height: 1.3;

        white-space: normal;
        overflow-wrap: anywhere;
        word-break: normal;
      }

      .inicio-mini-tipo {
        display: block;

        color: var(--c-tx-64736b);
        font-size: 11px;
        line-height: 1.4;
      }

      .inicio-mini-saldo {
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-width: 0;
      }

      .inicio-mini-etiqueta {
        color: var(--c-tx-58675e);
        font-size: 11px;
        line-height: 1.3;
      }

      .inicio-mini-monto {
        color: var(--c-tx-15291f);

        font-size: 15px;
        font-weight: 900;
        line-height: 1.3;

        font-variant-numeric: tabular-nums;
        white-space: nowrap;
      }

      .inicio-mini-disponible {
        display: flex;
        flex-direction: column;
        gap: 4px;

        min-width: 0;
        padding: 9px;

        border-radius: 11px;
        background: var(--c-bg-dff1e7);
      }

      .inicio-mini-disponible .inicio-mini-etiqueta {
        color: var(--c-tx-28664f);
        font-weight: 700;
      }

      .inicio-mini-disponible .inicio-mini-monto {
        color: var(--c-tx-075b42);
      }

      .inicio-mini-disponible.sin-dato {
        background: var(--c-bg-e8e9e7);
      }

      .inicio-mini-disponible.sin-dato
      .inicio-mini-monto {
        color: var(--c-tx-66736b);
      }

      .inicio-mini-disponible.negativo,
      .inicio-mini-disponible.con-reserva {
        background: var(--c-bg-ffe8e2);
      }

      .inicio-mini-disponible.negativo
      .inicio-mini-etiqueta,
      .inicio-mini-disponible.con-reserva
      .inicio-mini-etiqueta {
        color: var(--c-tx-8f2d1e);
      }

      .inicio-mini-disponible.negativo
      .inicio-mini-monto,
      .inicio-mini-disponible.con-reserva
      .inicio-mini-monto {
        color: var(--c-tx-a73525);
      }

      .inicio-mini-detalles {
        display: flex;
        align-items: center;
        justify-content: center;

        width: 100%;
        min-height: 34px;

        margin-top: auto;
        padding: 8px 5px;

        border: 1px solid var(--c-bd-c9dfd1);
        border-radius: 999px;

        background: var(--c-bg-ffffff);
        color: var(--c-tx-087453);

        font: inherit;
        font-size: 12px;
        font-weight: 800;

        cursor: pointer;
      }

      .inicio-mini-detalles:hover {
        background: var(--c-bg-e3f3e9);
      }

      .inicio-mini-pista {
        margin: 0;

        color: var(--c-tx-65736b);
        font-size: 11px;
        line-height: 1.4;
      }

      .inicio-cuentas-aviso {
        margin: 0;

        padding: 10px 12px;
        border-radius: 12px;

        background: var(--c-bg-fff2d9);
        color: var(--c-tx-81531e);

        font-size: 12px;
        line-height: 1.5;
      }

      .inicio-cuentas-aviso[hidden] {
        display: none;
      }

      /* Ventana flotante de detalles */

      .inicio-dialogo-cuenta {
        box-sizing: border-box;

        width: min(92vw, 440px);
        max-width: 440px;
        max-height: 85dvh;

        padding: 0;
        margin: auto;

        border: 0;
        border-radius: 20px;

        background: var(--c-bg-ffffff);
        color: var(--c-tx-142b21);

        overflow: hidden;
        box-shadow: 0 20px 65px #0004;
      }

      .inicio-dialogo-cuenta[open] {
        display: flex;
        flex-direction: column;
      }

      .inicio-dialogo-cuenta::backdrop {
        background: rgba(0, 0, 0, .55);
      }

      .inicio-dialogo-cabecera {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;

        padding: 19px 19px 15px;

        border-bottom: 1px solid var(--c-bd-e2eae5);
      }

      .inicio-dialogo-titulo {
        display: flex;
        flex-direction: column;
        gap: 6px;

        min-width: 0;
      }

      .inicio-dialogo-titulo h2 {
        margin: 0;

        font-size: 20px;
        line-height: 1.3;
        overflow-wrap: anywhere;
      }

      .inicio-dialogo-titulo p {
        margin: 0;

        font-size: 13px;
        color: var(--c-tx-67756d);
      }

      .inicio-dialogo-cerrar {
        flex-shrink: 0;

        display: flex;
        align-items: center;
        justify-content: center;

        width: 36px;
        height: 36px;

        border: 0;
        border-radius: 50%;

        background: var(--c-bg-edf2ee);
        color: var(--c-tx-263a30);

        font-size: 24px;
        cursor: pointer;
      }

      .inicio-dialogo-cuerpo {
        display: flex;
        flex-direction: column;
        gap: 14px;

        padding: 19px;
        min-height: 0;

        overflow-y: auto;
        overscroll-behavior: contain;
      }

      .inicio-dialogo-cifra {
        display: flex;
        flex-direction: column;
        gap: 5px;

        padding: 14px;

        border-radius: 14px;
        background: var(--c-bg-f0f4f1);
      }

      .inicio-dialogo-cifra span {
        font-size: 12px;
        color: var(--c-tx-607268);
      }

      .inicio-dialogo-cifra strong {
        font-size: 23px;
        font-weight: 900;

        overflow-wrap: anywhere;
      }

      .inicio-dialogo-cifra.libre {
        background: var(--c-bg-dff2e7);
      }

      .inicio-dialogo-cifra.libre strong {
        color: var(--c-tx-075b42);
      }

      .inicio-dialogo-cifra.negativa {
        background: var(--c-bg-ffe8e2);
      }

      .inicio-dialogo-cifra.negativa strong {
        color: var(--c-tx-a73525);
      }

      .inicio-dialogo-fila {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;

        font-size: 13px;
        line-height: 1.5;
      }

      .inicio-dialogo-fila span {
        color: var(--c-tx-5c6b62);
      }

      .inicio-dialogo-fila strong {
        text-align: right;
        overflow-wrap: anywhere;
      }

      .inicio-dialogo-aviso {
        margin: 0;

        padding: 11px;
        border-radius: 11px;

        background: var(--c-bg-fff3dd);
        color: var(--c-tx-875521);

        font-size: 12px;
        line-height: 1.5;
      }

      .inicio-dialogo-pie {
        display: flex;
        gap: 9px;

        padding: 15px 19px;

        border-top: 1px solid var(--c-bd-e2eae5);
      }

      .inicio-dialogo-pie a,
      .inicio-dialogo-pie button {
        display: flex;
        align-items: center;
        justify-content: center;

        flex: 1;

        min-height: 43px;
        padding: 9px;

        box-sizing: border-box;
        border-radius: 999px;

        font: inherit;
        font-size: 13px;
        font-weight: 800;

        cursor: pointer;
        text-decoration: none;
      }

      .inicio-dialogo-pie button {
        border: 1px solid var(--c-bd-d5e3da);
        background: var(--c-bg-f3f6f4);
        color: var(--c-tx-263b30);
      }

      .inicio-dialogo-editar {
        border: 1px solid var(--c-bd-087a59);
        background: var(--c-bg-087a59);
        color: var(--c-tx-ffffff) !important;
      }

      @media (max-width: 380px) {
        .inicio-carrusel-cuentas {
          grid-auto-columns: 150px;
        }

        .inicio-mini-monto {
          font-size: 14px;
        }

        .inicio-dialogo-cabecera,
        .inicio-dialogo-cuerpo,
        .inicio-dialogo-pie {
          padding: 15px;
        }
      }
    </style>


    <header class="banda banda-inicio">
      <div class="banda-fila espaciada">
        <span
          class="avatar"
          aria-hidden="true"
        >
          ${esc(iniciales)}
        </span>

        <div class="banda-acciones">
          <button
            type="button"
            class="btn-icono"
            id="btn-ocultar"
            aria-label="Ocultar o mostrar saldos"
          >
            ${icono('ojo')}
          </button>

          <a
            class="btn-icono"
            href="#/cambiar-contrasena"
            aria-label="Cambiar contraseña"
            title="Cambiar contraseña"
          >
            <svg
              aria-hidden="true"
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            >
              <rect x="5" y="11"
                width="14" height="10" rx="2"/>

              <path d="M8 11V7a4 4 0 0 1 8 0v4M12 15v2"/>
            </svg>
          </a>

          <button
            type="button"
            class="btn-icono"
            id="btn-salir"
            aria-label="Cerrar sesión"
          >
            ${icono('salir')}
          </button>
        </div>
      </div>

      <p class="saludo">
        Hola, ${esc(usuario.nombre_1 || '')}
      </p>

      <div class="saldo-general">
        <span class="saldo-etiqueta">
          Saldo general real
        </span>

        <span
          class="saldo-valor monto"
          id="saldo-general"
        >
          …
        </span>

        <div class="saldo-meta">
          <a
            class="pildora-oro"
            id="pendientes"
            href="#/movimientos"
            hidden
          ></a>

          <span id="saldo-detalle"></span>
        </div>
      </div>
    </header>


    <nav
      class="acciones"
      aria-label="Acciones rápidas"
    >
      <a href="#/registrar" class="accion">
        <span class="accion-circulo lleno">
          ${icono('mas', 26)}
        </span>
        Registrar
      </a>

      <a href="#/transferir" class="accion">
        <span class="accion-circulo lleno">
          ${icono('transferir', 24)}
        </span>
        Transferir
      </a>

      <a href="#/deudas" class="accion">
        <span class="accion-circulo">
          ${icono('deudas', 24)}
        </span>
        Deudas
      </a>

      <a href="#/metas" class="accion">
        <span class="accion-circulo">
          ${icono('metas', 24)}
        </span>
        Metas
      </a>
    </nav>


    <section class="seccion">
      <div class="seccion-titulo">
        <h2>Mis cuentas</h2>

        <a href="#/nueva-cuenta">
          + Nueva cuenta
        </a>
      </div>

      <p
        id="cuentas-aviso"
        class="inicio-cuentas-aviso"
        hidden
      ></p>

      <div
        id="cuentas"
        class="inicio-carrusel-cuentas"
        aria-label="Cuentas financieras. Desplaza horizontalmente para ver más."
        tabindex="0"
      >
        ${cargando()}
      </div>

      <p
        id="cuentas-pista"
        class="inicio-mini-pista"
        hidden
      >
        Desliza horizontalmente para ver las demás cuentas.
      </p>
    </section>


    <section class="seccion">
      <div class="seccion-titulo">
        <h2>Categorías financieras</h2>

        <a href="#/categorias">
          Administrar
        </a>
      </div>

      <p class="nota">
        Organiza tus ingresos y gastos
        mediante categorías personalizadas.
      </p>
    </section>


    <section class="seccion">
      <div class="tarjeta-gris" id="resumen">
        <div class="seccion-titulo">
          <h2>Resumen de ${nombreMes(mes)}</h2>
        </div>

        <div id="resumen-cuerpo">
          ${cargando()}
        </div>
      </div>
    </section>


    <section class="seccion">
      <div class="seccion-titulo">
        <h2>Últimos movimientos</h2>

        <a href="#/movimientos">
          Ver todos
        </a>
      </div>

      <div id="ultimos">
        ${cargando()}
      </div>
    </section>


    <dialog
      id="cuenta-dialogo"
      class="inicio-dialogo-cuenta"
      aria-labelledby="cuenta-dialogo-titulo"
    ></dialog>
  `;


  if (saldosOcultos()) {
    c.classList.add('ocultar-montos');
  }

  c.querySelector('#btn-ocultar')
    .addEventListener('click', () => {
      const ocultar = !c.classList.contains(
        'ocultar-montos'
      );

      c.classList.toggle(
        'ocultar-montos',
        ocultar
      );

      try {
        localStorage.setItem(
          'fp:ocultar',
          ocultar ? '1' : '0'
        );
      } catch {
        // Almacenamiento no disponible.
      }
    });


  c.querySelector('#btn-salir')
    .addEventListener('click', () => {
      cerrarSesion();
      location.hash = '#/login';
    });


  pintarPendientes(c);
  pintarCuentas(c);
  pintarResumen(c, anio, mes);
  pintarUltimos(c, anio, mes);
}


// ------------------------------------
// OPERACIONES PENDIENTES
// ------------------------------------

async function pintarPendientes(c) {
  const el = c.querySelector('#pendientes');

  if (!el) return;

  try {
    const lista = await operacionesLocales();

    if (!Array.isArray(lista) || !lista.length) {
      return;
    }

    const errores = lista.filter(
      op => op.estado_sync === 'ERROR'
    ).length;

    el.textContent = errores
      ? `${errores} rechazada(s) · revisar`
      : `${lista.length} sin sincronizar`;

    el.hidden = false;

  } catch (error) {
    console.warn(
      'No se pudieron consultar pendientes:',
      error
    );
  }
}


// ------------------------------------
// CARRUSEL Y DETALLES DE CUENTAS
// ------------------------------------

async function pintarCuentas(c) {
  const caja = c.querySelector('#cuentas');
  const aviso = c.querySelector('#cuentas-aviso');
  const pista = c.querySelector('#cuentas-pista');
  const dialogo = c.querySelector('#cuenta-dialogo');

  const usuarioInicial = Number(
    obtenerUsuario()?.id_usuario
  );

  const mismaSesion = () =>
    Number.isSafeInteger(usuarioInicial) &&
    usuarioInicial > 0 &&
    Number(obtenerUsuario()?.id_usuario) === usuarioInicial;

  let datos;
  let cuentasCache = false;

  try {
    datos = await obtenerMisCuentas();

    if (!mismaSesion()) return;

    guardarCache('cuentas', datos);

  } catch (error) {
    const cache = leerCache('cuentas');

    if (
      !(error instanceof ErrorDeRed) ||
      !Array.isArray(cache?.datos?.cuentas)
    ) {
      caja.innerHTML = errorCarga(error);

      c.querySelector('#saldo-general')
        .textContent = '—';

      return;
    }

    datos = cache.datos;
    cuentasCache = true;
  }


  let consulta = null;

  try {
    consulta = await consultarReservasVisibles();

  } catch (error) {
    console.warn(
      'No se pudieron consultar reservas:',
      error
    );
  }

  if (!mismaSesion()) return;

  const cuentas = Array.isArray(datos.cuentas)
    ? datos.cuentas
    : [];

  const saldoGeneral = Number(datos.saldo_general);

  c.querySelector('#saldo-general')
    .textContent = cop(saldoGeneral);


  // RESUMEN GENERAL

  const todasVerificadas = (
    consulta !== null &&
    cuentas.every(cuenta =>
      encontrarSaldoReserva(
        consulta,
        cuenta.id_cuenta
      ) !== null
    )
  );

  const reservadoTotal = todasVerificadas
    ? cuentas.reduce((total, cuenta) => {
        const saldo = encontrarSaldoReserva(
          consulta,
          cuenta.id_cuenta
        );

        return total + Number(
          saldo.monto_reservado || 0
        );
      }, 0)
    : null;

  const detalleGeneral = c.querySelector(
    '#saldo-detalle'
  );

  if (reservadoTotal !== null) {
    detalleGeneral.innerHTML = `
      ${cuentas.length} cuenta(s)
      · Reservado

      <span class="monto">
        ${cop(reservadoTotal)}
      </span>

      · Libre

      <span class="monto">
        ${cop(saldoGeneral - reservadoTotal)}
      </span>
    `;

  } else {
    detalleGeneral.textContent =
      `${cuentas.length} cuenta(s) · ` +
      'Reservas sin verificar';
  }


  // MENSAJE GLOBAL DE DATOS GUARDADOS

  const datosGuardados = Boolean(
    cuentasCache || consulta?.desdeCache
  );

  if (datosGuardados) {
    aviso.hidden = false;

    aviso.textContent =
      'Estás consultando datos guardados. ' +
      'El saldo disponible puede haber cambiado ' +
      'y será verificado al sincronizar.';

  } else if (!consulta) {
    aviso.hidden = false;

    aviso.textContent =
      'No se pudieron consultar las reservas. ' +
      'El saldo libre se mostrará cuando ' +
      'la información esté disponible.';

  } else {
    aviso.hidden = true;
    aviso.textContent = '';
  }


  // TARJETAS DEL CARRUSEL

  if (!cuentas.length) {
    caja.innerHTML = `
      <div class="vacio">
        <p>No tienes cuentas financieras.</p>

        <a href="#/nueva-cuenta">
          Crear mi primera cuenta
        </a>
      </div>
    `;

    pista.hidden = true;
    return;
  }

  pista.hidden = cuentas.length <= 2;

  caja.innerHTML = cuentas.map(cuenta => {
    const reserva = encontrarSaldoReserva(
      consulta,
      cuenta.id_cuenta
    );

    const real = Number(
      reserva?.saldo_real ??
      cuenta.saldo_actual
    );

    const libre = reserva
      ? Number(reserva.saldo_libre)
      : null;

    const reservado = reserva
      ? Number(reserva.monto_reservado || 0)
      : 0;

    const activa =
      cuenta.estado === 'ACTIVA';

    const tipo = (
      NOMBRES_TIPO[cuenta.tipo_cuenta] ||
      cuenta.tipo_cuenta
    );

    const inicial = cuenta.tipo_cuenta === 'EFECTIVO'
      ? '$'
      : String(
          cuenta.nombre_cuenta || '?'
        ).charAt(0).toUpperCase();

    const claseLibre = libre === null
      ? 'sin-dato'
      : libre < 0
        ? 'negativo'
        : reservado > 0
          ? 'con-reserva'
          : '';

    return `
      <article
        class="inicio-mini-cuenta${
          activa ? '' : ' inactiva'
        }"
      >

        <span
          class="inicio-mini-icono"
          aria-hidden="true"
        >
          ${esc(inicial)}
        </span>

        <div class="inicio-mini-identidad">

          <strong
            class="inicio-mini-nombre"
            title="${esc(cuenta.nombre_cuenta)}"
          >
            ${esc(cuenta.nombre_cuenta)}
          </strong>

          <span class="inicio-mini-tipo">
            ${esc(tipo)}
          </span>
        </div>

        <div class="inicio-mini-saldo">

          <span class="inicio-mini-etiqueta">
            Saldo real
          </span>

          <strong class="inicio-mini-monto monto">
            ${cop(real)}
          </strong>
        </div>

        <div
          class="inicio-mini-disponible ${claseLibre}"
        >
          <span class="inicio-mini-etiqueta">
            Disponible
          </span>

          <strong class="inicio-mini-monto monto">
            ${
              libre === null
                ? '—'
                : cop(libre)
            }
          </strong>
        </div>

        <button
          type="button"
          class="inicio-mini-detalles"
          data-cuenta-detalle="${
            Number(cuenta.id_cuenta)
          }"
          aria-label="Ver detalles de ${
            esc(cuenta.nombre_cuenta)
          }"
        >
          Ver detalles
        </button>

      </article>
    `;
  }).join('');


  // ABRIR DETALLES EN VENTANA FLOTANTE

  caja.addEventListener('click', evento => {
    const boton = evento.target.closest(
      'button[data-cuenta-detalle]'
    );

    if (!boton) return;
    if (!mismaSesion()) return;

    const id = Number(
      boton.dataset.cuentaDetalle
    );

    const cuenta = cuentas.find(
      item => Number(item.id_cuenta) === id
    );

    if (!cuenta) return;

    const reserva = encontrarSaldoReserva(
      consulta,
      id
    );

    const real = Number(
      reserva?.saldo_real ??
      cuenta.saldo_actual
    );

    const reservado = reserva
      ? Number(reserva.monto_reservado)
      : null;

    const libre = reserva
      ? Number(reserva.saldo_libre)
      : null;

    const tipo = (
      NOMBRES_TIPO[cuenta.tipo_cuenta] ||
      cuenta.tipo_cuenta
    );

    const activa =
      cuenta.estado === 'ACTIVA';

    dialogo.innerHTML = `
      <div class="inicio-dialogo-cabecera">
        <div class="inicio-dialogo-titulo">

          <h2 id="cuenta-dialogo-titulo">
            ${esc(cuenta.nombre_cuenta)}
          </h2>

          <p>
            ${esc(tipo)}
            · ${activa ? 'Activa' : 'Inactiva'}
          </p>
        </div>

        <button
          type="button"
          class="inicio-dialogo-cerrar"
          data-cerrar-dialogo
          aria-label="Cerrar detalles"
        >
          ×
        </button>
      </div>


      <div class="inicio-dialogo-cuerpo">

        ${
          cuenta.institucion
            ? `
              <div class="inicio-dialogo-fila">
                <span>Institución</span>

                <strong>
                  ${esc(cuenta.institucion)}
                </strong>
              </div>
            `
            : ''
        }

        <div class="inicio-dialogo-cifra">
          <span>Saldo real de la cuenta</span>

          <strong class="monto">
            ${cop(real)}
          </strong>
        </div>

        <div class="inicio-dialogo-fila">
          <span>Dinero reservado para metas</span>

          <strong class="monto">
            ${
              reservado === null
                ? 'Sin verificar'
                : cop(reservado)
            }
          </strong>
        </div>

        <div
          class="inicio-dialogo-cifra libre ${
            libre !== null && libre < 0
              ? 'negativa'
              : ''
          }"
        >
          <span>Disponible para gastar</span>

          <strong class="monto">
            ${
              libre === null
                ? 'Sin verificar'
                : cop(libre)
            }
          </strong>
        </div>

        ${
          datosGuardados
            ? `
              <p class="inicio-dialogo-aviso">
                Estos importes provienen de una
                consulta guardada. Pueden haber
                cambiado en el servidor.
              </p>
            `
            : ''
        }

        ${
          reservado !== null && reservado > 0
            ? `
              <a
                class="enlace"
                href="#/metas"
              >
                Ver y administrar reservas en Metas
              </a>
            `
            : ''
        }

      </div>


      <div class="inicio-dialogo-pie">

        <button
          type="button"
          data-cerrar-dialogo
        >
          Cerrar
        </button>

        ${
          activa
            ? `
              <a
                class="inicio-dialogo-editar"
                href="#/editar-cuenta/${id}"
              >
                Editar cuenta
              </a>
            `
            : ''
        }

      </div>
    `;

    if (dialogo.open) {
      dialogo.close();
    }

    dialogo.showModal();
  });


  dialogo.addEventListener('click', evento => {
    if (
      evento.target.closest(
        '[data-cerrar-dialogo]'
      )
    ) {
      dialogo.close();
    }
  });
}


// ------------------------------------
// RESUMEN MENSUAL
// ------------------------------------

async function pintarResumen(c, anio, mes) {
  const caja = c.querySelector(
    '#resumen-cuerpo'
  );

  try {
    const respuesta = await obtenerResumenMensual(
      anio,
      mes
    );

    const ingresos = Number(
      respuesta.ingresos_ordinarios
    );

    const gastos = Number(
      respuesta.gastos_ordinarios
    );

    const porcentajeGastado = ingresos > 0
      ? Math.min(
          100,
          Math.round(
            gastos / ingresos * 100
          )
        )
      : 0;

    caja.innerHTML = `
      <div class="resumen-cifras">

        <div class="mini">
          <span>Ingresos</span>

          <strong class="ingreso monto">
            ${cop(ingresos)}
          </strong>
        </div>

        <div class="mini">
          <span>Gastos</span>

          <strong class="gasto monto">
            ${cop(gastos)}
          </strong>
        </div>
      </div>

      <div
        class="barra"
        role="img"
        aria-label="Gastaste el ${
          porcentajeGastado
        } % de tus ingresos"
      >
        <span
          class="barra-gasto"
          style="width:${
            porcentajeGastado
          }%"
        ></span>
      </div>

      <div class="resumen-pie">
        <span>
          Gastaste el
          ${porcentajeGastado} %
          de tus ingresos
        </span>

        <span>
          GMF

          <span class="monto">
            ${cop(respuesta.gmf_total)}
          </span>
        </span>
      </div>
    `;

  } catch (error) {
    caja.innerHTML = errorCarga(error);
  }
}


// ------------------------------------
// FILA DE MOVIMIENTO
// CONSERVADA PARA OTRAS VISTAS
// ------------------------------------

export function filaMovimiento(m, opciones) {
  const accionable = Boolean(
    opciones &&
    opciones.accionable === true
  );

  const esGasto = m.tipo === 'GASTO';
  const interno = m.origen !== 'NORMAL';

  const clase = interno
    ? 'neutro'
    : esGasto
      ? 'gasto'
      : 'ingreso';

  const icon = m.origen === 'TRANSFERENCIA'
    ? 'transferir'
    : m.origen === 'OBLIGACION'
      ? 'deudas'
      : esGasto
        ? 'comida'
        : 'maletin';

  const detalle = [
    m.origen === 'NORMAL'
      ? m.nombre_categoria
      : m.origen === 'TRANSFERENCIA'
        ? 'Transferencia'
        : 'Obligación',
    m.nombre_cuenta,
    fechaCorta(m.fecha_movimiento)
  ].filter(Boolean).map(esc).join(' · ');

  const signo = esGasto ? '− ' : '+ ';

  const abre = accionable
    ? `
      <button
        type="button"
        class="movimiento accionable${
          m.estado === 'ANULADO'
            ? ' anulado'
            : ''
        }"
        data-id="${m.id_movimiento}"
      >
    `
    : `
      <article class="movimiento${
        m.estado === 'ANULADO'
          ? ' anulado'
          : ''
      }">
    `;

  return `
    ${abre}

      <span
        class="mov-icono ${clase}"
        aria-hidden="true"
      >
        ${icono(icon, 19)}
      </span>

      <span class="mov-texto">
        <strong>
          ${
            esc(
              m.descripcion ||
              m.nombre_categoria ||
              'Movimiento'
            )
          }
        </strong>

        <span>
          ${detalle}

          ${
            m.estado === 'ANULADO'
              ? ' · anulado'
              : ''
          }
        </span>
      </span>

      <span
        class="mov-monto ${clase} monto"
      >
        ${signo}${cop(m.monto)}
      </span>

    ${
      accionable
        ? '</button>'
        : '</article>'
    }
  `;
}


// ------------------------------------
// ÚLTIMOS MOVIMIENTOS
// ------------------------------------

async function pintarUltimos(c, anio, mes) {
  const caja = c.querySelector(
    '#ultimos'
  );

  try {
    const historial =
      await obtenerHistorialMensual(
        anio,
        mes
      );

    const lista = historial.movimientos
      .slice(0, 5);

    caja.innerHTML = lista.length
      ? `
        <div class="lista">
          ${
            lista.map(filaMovimiento).join('')
          }
        </div>
      `
      : `
        <p class="vacio">
          Sin movimientos este mes.
        </p>
      `;

  } catch (error) {
    caja.innerHTML = errorCarga(error);
  }
}