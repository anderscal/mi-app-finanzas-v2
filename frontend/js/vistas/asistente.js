import { banda } from './comun.js';

import {
  consultarContextoRAG,
  preguntarRAG
} from '../rag-api.js';

import {
  obtenerToken,
  obtenerUsuario
} from '../sesion.js';

import {
  ErrorApi,
  ErrorDeRed
} from '../api.js';


const SUGERENCIAS = [
  [
    'Saldo disponible',
    '¿Cuánto dinero tengo disponible sin afectar mis metas?'
  ],
  [
    'Gastos del mes',
    '¿Cuánto he gastado este mes por categoría?'
  ],
  [
    'Mis metas',
    '¿Cómo van mis metas de ahorro?'
  ],
  [
    'GMF del mes',
    '¿Cuánto pagué de GMF este mes?'
  ],
  [
    'Presupuestos',
    '¿Cómo están mis presupuestos este mes?'
  ]
];


const ETIQUETAS = {
  cuentas: 'Cuentas',
  movimientos: 'Movimientos',
  transferencias: 'Transferencias',
  obligaciones: 'Obligaciones',
  metas: 'Metas',
  presupuestos: 'Presupuestos',
  reservas: 'Reservas',
  categorias: 'Categorías',

  rdf_reservas: 'Relaciones de reservas',
  rdf_movimientos: 'Relaciones de movimientos',
  rdf_transferencias: 'Relaciones de transferencias',
  rdf_categorias: 'Categorías relacionadas',
  rdf_obligaciones: 'Obligaciones relacionadas',
  rdf_presupuestos: 'Presupuestos relacionados',

  saldo_real: 'Saldo real',
  saldo_libre: 'Saldo disponible',
  reservado: 'Reservado',
  reservado_neto: 'Reserva neta',

  monto_original: 'Monto original',
  monto_con_gmf: 'Monto con GMF',

  tipo_cuenta: 'Tipo de cuenta',
  cuenta_origen: 'Cuenta de origen',
  cuenta_destino: 'Cuenta de destino',

  fecha_inicio: 'Fecha inicial',
  fecha_vencimiento: 'Vencimiento',
  fecha_objetivo: 'Fecha objetivo',

  porcentaje_usado: 'Porcentaje usado',
  anio: 'Año',
  limite: 'Límite',
  gmf: 'GMF',

  entidad: 'Entidad',
  valor: 'Resultado',
  cantidad: 'Registros incluidos',

  listar: 'Listado',
  contar: 'Conteo',
  sumar: 'Suma',
  promedio: 'Promedio',
  minimo: 'Mínimo',
  maximo: 'Máximo',

  igual: '=',
  distinto: '≠',
  mayor: '>',
  menor: '<',
  mayor_igual: '≥',
  menor_igual: '≤',
  contiene: 'contiene',
  es_nulo: 'sin valor',
  no_nulo: 'con valor'
};


function etiqueta(valor) {
  const s = String(valor ?? '');

  return Object.hasOwn(ETIQUETAS, s)
    ? ETIQUETAS[s]
    : s.replaceAll('_', ' ');
}


function lista(valor) {
  return Array.isArray(valor) ? valor : [];
}


function dato(valor) {

  if (valor == null) return 'Sin dato';

  if (typeof valor === 'boolean') {
    return valor ? 'Sí' : 'No';
  }

  return typeof valor === 'object'
    ? JSON.stringify(valor)
    : String(valor);
}


// ======================================
// COMPONENTES SEGUROS
// ======================================

function nodo(tipo, texto, clase) {

  const el = document.createElement(tipo);

  if (texto !== undefined) {
    el.textContent = texto;
  }

  if (clase) {
    el.className = clase;
  }

  return el;
}


function desplegable(titulo) {

  const el = nodo(
    'details',
    undefined,
    'rag-detalle'
  );

  el.append(nodo('summary', titulo));

  return el;
}


function jsonTecnico(datos) {

  const el = desplegable(
    'Datos técnicos (JSON)'
  );

  el.append(
    nodo('pre', JSON.stringify(datos, null, 2))
  );

  return el;
}


function textoSeguro(el, contenido) {

  el.replaceChildren();

  for (const parte of String(
    contenido ?? ''
  ).split(/(\*\*[^*\n]+\*\*)/g)) {

    if (!parte) continue;

    el.append(

      /^\*\*[^*\n]+\*\*$/.test(parte)

        ? nodo(
            'strong',
            parte.slice(2, -2)
          )

        : document.createTextNode(parte)
    );
  }
}


// ======================================
// MENSAJES DE ERROR
// ======================================

function errorVisible(error, modo) {

  if (error instanceof ErrorDeRed) {

    return 'Sin conexión con el servicio.';
  }

  if (error instanceof ErrorApi) {

    switch (error.estado) {

      case 401:
        return 'Tu sesión venció. Inicia sesión.';

      case 403:
        return 'No tienes autorización para esta consulta.';

      case 409:
        return 'No pude verificar los datos. Intenta más tarde.';

      case 422:
        return modo === 'ia'
          ? 'No pude procesar tu consulta. Intenta reformularla.'
          : 'No pude completar el diagnóstico.';

      case 429:
        return 'Límite de consultas alcanzado. Intenta más tarde.';

      default:

        if (error.estado >= 500) {

          return 'Servicio temporalmente no disponible.';
        }
    }
  }

  return 'No se pudo completar la consulta.';
}


// ======================================
// EVIDENCIA FINANCIERA
// ======================================

const MONETARIOS = new Set([
  'saldo_real',
  'saldo_libre',
  'reservado',
  'reservado_neto',
  'monto',
  'monto_original',
  'monto_con_gmf',
  'gmf',
  'abonado',
  'pendiente',
  'objetivo',
  'acumulado',
  'limite',
  'gastado',
  'disponible'
]);


function cabeceraCampo(k, evidencia) {

  const campo = (
    k === 'valor' &&
    evidencia?.operacion !== 'contar'
  )
    ? evidencia?.campo_agregado
    : k;

  const unidad = MONETARIOS.has(campo)

    ? ' (COP)'

    : [
        'progreso',
        'porcentaje_usado'
      ].includes(campo)

      ? ' (%)'

      : '';

  return etiqueta(k) + unidad;
}


function tabla(filas, evidencia) {

  const registros = lista(filas).filter(

    f => f &&
      typeof f === 'object' &&
      !Array.isArray(f)
  );

  if (!registros.length) {

    return nodo(
      'p',
      'Sin registros recuperados.'
    );
  }

  const columnas = [
    ...new Set(
      registros.flatMap(f => Object.keys(f))
    )
  ];

  const caja = nodo(
    'div',
    undefined,
    'rag-tabla'
  );

  caja.tabIndex = 0;

  caja.setAttribute('role', 'region');

  caja.setAttribute(
    'aria-label',
    'Resultados recuperados'
  );

  const t = nodo('table');
  const thead = nodo('thead');
  const cab = nodo('tr');

  for (const k of columnas) {

    const th = nodo(
      'th',
      cabeceraCampo(k, evidencia)
    );

    th.scope = 'col';

    cab.append(th);
  }

  thead.append(cab);
  t.append(thead);

  const tbody = nodo('tbody');

  for (const fila of registros) {

    const tr = nodo('tr');

    for (const k of columnas) {

      tr.append(
        nodo(
          'td',
          dato(
            Object.hasOwn(fila, k)
              ? fila[k]
              : null
          )
        )
      );
    }

    tbody.append(tr);
  }

  t.append(tbody);
  caja.append(t);

  return caja;
}


function agregarEvidencia(articulo, respuesta) {

  const fuentes = lista(respuesta.fuentes);

  const evidencias = lista(respuesta.evidencia);

  const limitaciones = lista(
    respuesta.limitaciones
  );


  // Aviso visible incluso con el
  // desplegable cerrado.

  if (
    evidencias.some(
      e => e.truncado === true
    )
  ) {

    articulo.append(

      nodo(
        'p',
        'Resultados parciales: hay listados limitados.',
        'rag-alerta'
      )
    );
  }


  const detalles = desplegable(
    'Fuentes y evidencia'
  );

  detalles.append(

    nodo(
      'p',

      fuentes.length

        ? fuentes.map(
            f => dato(f.origen)
          ).join(' · ')

        : 'No se consultaron fuentes financieras.'
    )
  );


  for (const e of evidencias) {

    const bloque = desplegable(

      `[${dato(e.referencia)}] ` +
      `${etiqueta(e.entidad)} · ` +
      `${etiqueta(e.operacion)}`
    );


    if (e.campo_agregado) {

      bloque.append(
        nodo(
          'p',
          'Campo: ' + etiqueta(e.campo_agregado)
        )
      );
    }


    for (const f of lista(e.filtros)) {

      bloque.append(

        nodo(
          'p',

          `${etiqueta(f.campo)} ` +
          `${etiqueta(f.operador)}` +
          (
            f.valor == null
              ? ''
              : ' ' + dato(f.valor)
          )
        )
      );
    }


    if (lista(e.agrupar_por).length) {

      bloque.append(

        nodo(
          'p',

          'Agrupado por: ' +

          e.agrupar_por.map(etiqueta).join(', ')
        )
      );
    }


    bloque.append(
      nodo('p', 'Fuente: ' + dato(e.origen))
    );


    if (e.fecha_instantanea) {

      bloque.append(
        nodo(
          'p',
          'Instantánea RDF: ' +
          dato(e.fecha_instantanea)
        )
      );
    }


    if (e.vigencia_rdf) {

      bloque.append(
        nodo(
          'p',
          'Vigencia RDF: ' +
          dato(e.vigencia_rdf)
        )
      );
    }


    bloque.append(tabla(e.filas, e));


    if (e.truncado === true) {

      bloque.append(

        nodo(
          'p',

          `Listado limitado a ${dato(e.limite)} filas.`,

          'rag-alerta'
        )
      );
    }


    bloque.append(jsonTecnico(e));

    detalles.append(bloque);
  }


  for (const l of limitaciones) {

    detalles.append(
      nodo('p', dato(l))
    );
  }


  if (respuesta.modelo) {

    detalles.append(
      nodo(
        'p',
        'Modelo: ' + dato(respuesta.modelo)
      )
    );
  }


  detalles.append(

    nodo(
      'p',

      'Las fuentes corresponden a la evidencia ' +
      'entregada al asistente, no verifican cada afirmación.'
    )
  );

  articulo.append(detalles);
}


// ======================================
// DIAGNOSTICO SIN IA
// ======================================

function diagnostico(panel, contexto) {

  panel.replaceChildren(
    nodo('h3', 'Estado de las fuentes')
  );

  const conteos = contexto.postgresql?.conteos || {};

  panel.append(

    tabla(

      Object.entries(conteos).map(
        ([k, v]) => ({
          entidad: etiqueta(k),
          cantidad: v
        })
      )
    )
  );


  const rdf = contexto.fuseki || {};

  panel.append(
    nodo('p', 'Fuseki: ' + dato(rdf.vigencia))
  );

  panel.append(
    nodo(
      'p',
      'Instantánea: ' + dato(rdf.fecha_instantanea)
    )
  );


  for (const l of lista(contexto.limitaciones)) {

    panel.append(nodo('p', dato(l)));
  }

  panel.append(jsonTecnico(contexto));
}


// ======================================
// MENSAJES DE LA CONSULTA
// ======================================

function mensaje(chat, rol, texto) {

  const art = nodo(

    'article',

    undefined,

    'rag-mensaje ' +

    (
      rol === 'usuario'
        ? 'rag-usuario'
        : 'rag-respuesta'
    )
  );

  art.append(

    nodo(
      'div',

      rol === 'usuario'
        ? 'Tú'
        : 'Asistente',

      'rag-autor'
    )
  );

  const cuerpo = nodo(
    'div',
    undefined,
    'rag-texto'
  );

  textoSeguro(cuerpo, texto);

  art.append(cuerpo);
  chat.append(art);

  return { art, cuerpo };
}


// ======================================
// PANTALLA PRINCIPAL
// ======================================

export async function render(c) {

  const token = obtenerToken();

  const uid = Number(
    obtenerUsuario()?.id_usuario
  );


  const vigente = () => (

    c.isConnected &&

    location.hash === '#/asistente' &&

    !!token &&

    obtenerToken() === token &&

    uid > 0 &&

    Number(
      obtenerUsuario()?.id_usuario
    ) === uid
  );


  let ocupada = false;
  let controlador = null;


  c.innerHTML = `

    <style>

      .rag-contenido {
        display: grid;
        gap: 16px;
        padding: 18px 16px 28px;
        min-width: 0;
      }

      .rag-linea {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
      }

      .rag-linea h2 {
        font-size: 15px;
      }

      .rag-contenido .enlace {
        background: none;
        border: 0;
        color: var(--marca);
        font-weight: 700;
        padding: 8px 0;
        min-height: 44px;
      }

      .rag-sugerencias {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .rag-sugerencias button {
        border: 1px solid var(--linea);
        background: var(--gris);
        color: var(--tinta);
        border-radius: 999px;
        padding: 8px 12px;
        min-height: 40px;
        font-size: 12px;
        font-weight: 700;
      }

      .rag-chat {
        display: grid;
        gap: 10px;
        min-width: 0;
      }

      .rag-mensaje {
        min-width: 0;
        max-width: 100%;
        padding: 14px;
        border-radius: 18px;
        display: grid;
        gap: 8px;
        overflow-wrap: anywhere;
      }

      .rag-usuario {
        background: var(--marca-oscuro);
        color: white;
        justify-self: end;
        max-width: 88%;
      }

      .rag-respuesta {
        background: var(--gris);
        color: var(--tinta);
      }

      .rag-autor {
        font-size: 11px;
        font-weight: 700;
        opacity: .85;
      }

      .rag-texto {
        font-size: 14px;
        line-height: 1.6;
        white-space: pre-wrap;
      }

      .rag-form {
        display: grid;
        gap: 10px;
        min-width: 0;
      }

      .rag-form textarea {
        width: 100%;
        min-height: 100px;
        resize: vertical;
        padding: 12px;
        border: 1px solid var(--linea);
        border-radius: 14px;
        font: inherit;
        font-size: 16px;
        color: var(--tinta);
      }

      .rag-consentimiento {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        font-size: 13px;
        line-height: 1.5;
      }

      .rag-consentimiento input {
        flex: none;
        width: 20px;
        height: 20px;
        accent-color: var(--marca);
      }

      .rag-nota,
      .rag-detalle p {
        font-size: 12px;
        color: var(--tenue);
        line-height: 1.5;
      }

      .rag-contador {
        text-align: right;
        font-size: 12px;
        color: var(--tenue);
      }

      .rag-estado:empty,
      .rag-error:empty,
      .rag-chat:empty {
        display: none;
      }

      .rag-error,
      .rag-alerta {
        color: var(--gasto);
        font-size: 13px;
        font-weight: 700;
      }

      .rag-detalle {
        min-width: 0;
        border-top: 1px solid var(--linea);
        padding-top: 8px;
        font-size: 13px;
        overflow-wrap: anywhere;
      }

      .rag-detalle summary {
        cursor: pointer;
        font-weight: 700;
        padding: 8px 0;
      }

      .rag-detalle p {
        margin: 6px 0;
      }

      .rag-detalle pre {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        font-size: 11px;
        background: var(--fondo);
        padding: 8px;
      }

      .rag-tabla {
        max-width: 100%;
        overflow-x: auto;
        margin: 8px 0;
      }

      .rag-tabla table {
        border-collapse: collapse;
        width: 100%;
        font-size: 12px;
      }

      .rag-tabla th,
      .rag-tabla td {
        text-align: left;
        padding: 8px;
        border-bottom: 1px solid var(--linea);
        vertical-align: top;
        overflow-wrap: anywhere;
      }

      .rag-tabla th {
        background: var(--marca-suave);
        color: var(--marca-oscuro);
      }

      .rag-panel h3 {
        font-size: 14px;
        margin: 10px 0;
      }

      .rag-acciones .btn {
        width: 100%;
      }

    </style>


    ${banda('Asistente financiero', {
      subtitulo: 'Consulta tus finanzas.'
    })}


    <section class="rag-contenido">

      <div class="rag-linea">

        <h2>Consultas sugeridas</h2>

        <button
          id="rag-nuevo"
          type="button"
          class="enlace"
        >
          Nueva consulta
        </button>

      </div>


      <div
        class="rag-sugerencias"
        id="rag-sugerencias"
      ></div>


      <div
        id="rag-chat"
        class="rag-chat"
        role="log"
        aria-label="Consultas y respuestas"
        aria-live="polite"
      ></div>


      <form
        id="rag-form"
        class="rag-form"
      >

        <label for="rag-pregunta">
          ¿Qué quieres saber?
        </label>

        <textarea
          id="rag-pregunta"
          maxlength="400"
          minlength="5"
          required
          placeholder="Escribe tu pregunta…"
        ></textarea>


        <div
          id="rag-contador"
          class="rag-contador"
        >
          0 / 400
        </div>


        <label class="rag-consentimiento">

          <input
            type="checkbox"
            id="rag-consentimiento"
          >

          <span>
            Autorizo enviar mi pregunta y los
            datos financieros recuperados a
            Google Gemini, un servicio externo.
          </span>

        </label>


        <button
          type="submit"
          id="rag-enviar"
          class="btn btn-primario"
          disabled
        >
          Consultar
        </button>


        <p
          id="rag-estado"
          class="rag-nota rag-estado"
          role="status"
        ></p>


        <p
          id="rag-error"
          class="rag-error"
          role="alert"
        ></p>

      </form>


      <p class="rag-nota">
        La IA puede cometer errores.
        No incluye movimientos pendientes de sincronizar.
        Cada consulta es independiente.
      </p>


      <details class="rag-detalle">

        <summary>Información técnica</summary>

        <p>
          Diagnóstico de PostgreSQL y Fuseki.
          No interpreta preguntas ni utiliza Gemini.
        </p>

        <button
          id="rag-diagnostico"
          type="button"
          class="btn btn-secundario"
        >
          Diagnóstico sin IA
        </button>

        <section
          id="rag-panel"
          class="rag-panel"
          aria-live="polite"
        ></section>

      </details>

    </section>`;


  const $ = id => c.querySelector('#rag-' + id);

  const pregunta = $('pregunta');
  const consentimiento = $('consentimiento');

  const chat = $('chat');
  const enviar = $('enviar');
  const diag = $('diagnostico');

  const estado = $('estado');
  const error = $('error');
  const panel = $('panel');

  const sugerencias = $('sugerencias');
  const nuevo = $('nuevo');


  // ======================================
  // CONTROLES
  // ======================================

  function actualizar() {

    $('contador').textContent =
      `${pregunta.value.length} / 400`;

    pregunta.disabled =
      consentimiento.disabled =
      nuevo.disabled =
      ocupada;

    diag.disabled = ocupada;

    enviar.disabled = (

      ocupada ||

      !consentimiento.checked ||

      pregunta.value.trim().length < 5 ||

      pregunta.value.length > 400
    );


    for (
      const b of sugerencias.querySelectorAll(
        'button'
      )
    ) {

      b.disabled = ocupada;
    }
  }


  for (const [titulo, texto] of SUGERENCIAS) {

    const b = nodo('button', titulo);

    b.type = 'button';

    b.addEventListener('click', () => {

      pregunta.value = texto;

      consentimiento.checked = false;

      error.textContent = '';

      actualizar();

      pregunta.focus();
    });

    sugerencias.append(b);
  }


  pregunta.addEventListener('input', () => {

    consentimiento.checked = false;

    error.textContent = '';

    actualizar();
  });


  consentimiento.addEventListener(
    'change',
    actualizar
  );


  nuevo.addEventListener('click', () => {

    chat.replaceChildren();
    panel.replaceChildren();

    pregunta.value = '';

    consentimiento.checked = false;

    estado.textContent =
      error.textContent = '';

    actualizar();

    pregunta.focus();
  });


  // Cancelar la solicitud local si
  // se abandona la pantalla.

  const observador = new MutationObserver(() => {

    if (!c.isConnected) {

      controlador?.abort();

      observador.disconnect();
    }
  });

  observador.observe(
    c.parentNode,
    { childList: true }
  );


  // ======================================
  // CONSULTAR
  // ======================================

  async function consultar(modo) {

    if (ocupada || !vigente()) return;

    const ia = modo === 'ia';

    const texto = pregunta.value.trim();


    if (
      ia &&
      (
        texto.length < 5 ||

        texto.length > 400 ||

        !consentimiento.checked
      )
    ) {

      return;
    }


    error.textContent = '';


    if (!navigator.onLine) {

      error.textContent =
        'Necesitas conexión a internet.';

      return;
    }


    ocupada = true;

    controlador = new AbortController();

    actualizar();

    estado.textContent = ia

      ? 'Consultando…'

      : 'Comprobando fuentes…';


    let pendiente = null;


    try {

      if (ia) {

        mensaje(
          chat,
          'usuario',
          texto
        );

        pendiente = mensaje(
          chat,
          'asistente',
          'Consultando…'
        );


        const r = await preguntarRAG(

          texto,

          {
            autorizoEnvioIA: true,

            signal: controlador.signal
          }
        );


        if (!vigente()) return;


        if (
          typeof r.respuesta !== 'string' ||

          !r.respuesta.trim()
        ) {

          throw new Error('Respuesta vacía');
        }


        textoSeguro(
          pendiente.cuerpo,
          r.respuesta
        );

        agregarEvidencia(
          pendiente.art,
          r
        );


        pregunta.value = '';

        pendiente.art.scrollIntoView({
          block: 'nearest'
        });

      } else {

        panel.replaceChildren(
          nodo('p', 'Comprobando fuentes…')
        );


        const r = await consultarContextoRAG(

          'Diagnóstico general de fuentes',

          {
            signal: controlador.signal
          }
        );


        if (!vigente()) return;

        diagnostico(panel, r);
      }

    } catch (e) {

      if (vigente()) {

        pendiente?.art.remove();

        error.textContent =
          errorVisible(e, modo);


        if (!ia) {

          panel.replaceChildren(

            nodo(
              'p',
              errorVisible(e, modo),
              'rag-alerta'
            )
          );
        }
      }

    } finally {

      controlador = null;

      ocupada = false;


      if (vigente()) {

        if (ia) {

          consentimiento.checked = false;
        }

        estado.textContent = '';

        actualizar();
      }
    }
  }


  $('form').addEventListener('submit', ev => {

    ev.preventDefault();

    consultar('ia');
  });


  diag.addEventListener('click', () => {

    consultar('diagnostico');
  });


  actualizar();
}