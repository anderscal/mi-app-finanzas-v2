
import { banda } from './comun.js';

import {
  consultarContextoRAG,
  preguntarRAG
} from '../rag-api.js';

import {
  obtenerUsuario, obtenerToken
} from '../sesion.js';

import {
  ErrorApi,
  ErrorDeRed
} from '../api.js';


const SUGERENCIAS = [
  '¿Cuánto dinero tengo disponible sin afectar mis metas?',
  '¿Cuánto pagué de GMF este mes?',
  '¿En qué categorías estoy gastando más?',
  '¿Cómo van mis metas de ahorro?',
  '¿Cómo están mis presupuestos este mes?'
];


/**
 * Dibuja texto de Gemini sin interpretarlo como HTML.
 *
 * Reconoce **negrita** de manera básica.
 * Los textos se insertan usando textContent.
 */
function textoSeguro(contenedor, contenido) {
  contenedor.replaceChildren();

  const partes = String(
    contenido ?? ''
  ).split(/(\*\*[^*\n]+\*\*)/g);

  for (const parte of partes) {
    if (!parte) continue;

    if (
      parte.startsWith('**') &&
      parte.endsWith('**')
    ) {
      const fuerte = document.createElement('strong');

      fuerte.textContent = parte.slice(2, -2);

      contenedor.appendChild(fuerte);

    } else {
      contenedor.appendChild(
        document.createTextNode(parte)
      );
    }
  }
}


function textoError(error) {
  return error?.message || 'Ocurrió un error al consultar el asistente.';
}

function periodoTexto(periodo) {
  if (!periodo) {
    return 'Período no especificado';
  }

  const anio = Number(periodo.anio);
  const mes = Number(periodo.mes);

  if (
    !Number.isInteger(anio) ||
    !Number.isInteger(mes) ||
    mes < 1 ||
    mes > 12
  ) {
    return 'Período no especificado';
  }

  const meses = [
    'enero', 'febrero', 'marzo',
    'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre',
    'octubre', 'noviembre', 'diciembre'
  ];

  return `${meses[mes - 1]} de ${anio}`;
}


function crearMensaje(
  contenedor,
  rol,
  contenido
) {
  const articulo = document.createElement('article');

  articulo.className = (
    rol === 'usuario'
      ? 'rag-mensaje rag-mensaje-usuario'
      : 'rag-mensaje rag-mensaje-asistente'
  );

  const cabecera = document.createElement('div');

  cabecera.className = 'rag-mensaje-cabecera';

  cabecera.textContent = (
    rol === 'usuario'
      ? 'Tú'
      : 'Asistente financiero'
  );

  const cuerpo = document.createElement('div');

  cuerpo.className = 'rag-mensaje-texto';

  textoSeguro(cuerpo, contenido);

  articulo.append(
    cabecera,
    cuerpo
  );

  contenedor.appendChild(articulo);

  articulo.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest'
  });

  return {
    articulo,
    cuerpo
  };
}


function agregarFuentes(
  articulo,
  respuesta
) {
  const fuentes = Array.isArray(respuesta.fuentes)
    ? respuesta.fuentes
    : [];

  const detalles = document.createElement('div');

  detalles.className = 'rag-fuentes';

  const titulo = document.createElement('strong');

  titulo.textContent = 'Contexto recuperado:';

  detalles.appendChild(titulo);

  if (!fuentes.length) {
    const texto = document.createElement('span');

    texto.textContent = (
      'No se informaron fuentes.'
    );

    detalles.appendChild(texto);

  } else {
    for (const fuente of fuentes) {
      const etiqueta = document.createElement('span');

      etiqueta.className = 'rag-fuente';

      etiqueta.textContent = String(
        fuente.origen || 'Fuente'
      );

      detalles.appendChild(etiqueta);
    }
  }

  if (respuesta.modelo) {
    const modelo = document.createElement('span');

    modelo.className = 'rag-modelo';

    modelo.textContent = (
      'Modelo: ' + respuesta.modelo
    );

    detalles.appendChild(modelo);
  }

  if (respuesta.periodo) {
    const periodo = document.createElement('span');

    periodo.className = 'rag-modelo';

    periodo.textContent = (
      'Período: ' +
      periodoTexto(respuesta.periodo)
    );

    detalles.appendChild(periodo);
  }

  const nota = document.createElement('p');

  nota.className = 'rag-fuente-nota';

  nota.textContent = (
    'Estas son las fuentes entregadas al motor RAG. ' +
    'No significa que cada frase de la respuesta ' +
    'utilice ambas fuentes.'
  );

  detalles.appendChild(nota);

  articulo.appendChild(detalles);

  const evidencia = Array.isArray(respuesta.evidencia)
    ? respuesta.evidencia : [];

  for (const dato of evidencia) {
    articulo.appendChild(detallesJSON(
      'Ver evidencia [' + String(dato.referencia || '?') + '] · ' +
      String(dato.origen || 'Fuente'), dato
    ));
  }

  agregarLimitaciones(articulo, respuesta.limitaciones);
}


function detallesJSON(titulo, datos) {
  const detalles = document.createElement('details');
  detalles.className = 'rag-detalles';
  const resumen = document.createElement('summary');
  resumen.textContent = titulo;
  const codigo = document.createElement('pre');
  codigo.textContent = JSON.stringify(datos, null, 2);
  detalles.append(resumen, codigo);
  return detalles;
}

function agregarLimitaciones(contenedor, limitaciones) {
  if (!Array.isArray(limitaciones) || !limitaciones.length) return;
  const aviso = document.createElement('p');
  aviso.className = 'rag-contexto-fecha';
  aviso.textContent = 'Limitaciones: ' + limitaciones.join(' · ');
  contenedor.appendChild(aviso);
}

function mostrarEvidencia(contenedor, contexto) {
  contenedor.replaceChildren();
  const titulo = document.createElement('h3');
  titulo.textContent = 'Diagnóstico de fuentes sin IA';
  const alcance = document.createElement('p');
  alcance.textContent = contexto.alcance ||
    'Diagnóstico general: no interpreta la pregunta escrita.';
  const lista = document.createElement('ul');
  const conteos = contexto.postgresql?.conteos || {};
  const etiquetas = {
    cuentas: 'Cuentas financieras', movimientos: 'Movimientos',
    transferencias: 'Transferencias', obligaciones: 'Obligaciones',
    metas: 'Metas', presupuestos: 'Presupuestos',
    reservas: 'Relaciones de reservas', categorias: 'Categorías'
  };

  for (const [campo, cantidad] of Object.entries(conteos)) {
    const elemento = document.createElement('li');
    elemento.textContent = `${etiquetas[campo] || campo}: ${cantidad ?? 'No disponible'}`;
    lista.appendChild(elemento);
  }

  const rdf = contexto.fuseki || {};
  const fecha = document.createElement('p');
  fecha.className = 'rag-contexto-fecha';
  fecha.textContent = 'Última instantánea RDF: ' +
    (rdf.fecha_instantanea || 'No disponible') +
    ' · Vigencia: ' + (rdf.vigencia || 'No disponible');

  contenedor.append(titulo, alcance, lista, fecha,
    detallesJSON('Ver diagnóstico completo', contexto));

  agregarLimitaciones(contenedor, contexto.limitaciones);

  contenedor.hidden = false;
  contenedor.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/**
 * Vista principal del asistente.
 *
 * Las conversaciones se mantienen únicamente
 * en la pantalla actual. No se almacenan
 * en localStorage ni IndexedDB.
 */
export async function render(c) {
  const usuarioInicial = Number(
    obtenerUsuario()?.id_usuario
  );

  const tokenInicial = obtenerToken();
  let ocupada = false;
  let controlador = null;

  c.innerHTML = `
    <style>
      .rag-contenido {
        padding: 18px 16px 30px;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .rag-descripcion {
        background: var(--marca-suave);
        border-radius: 18px;
        padding: 14px;
        font-size: 13px;
        line-height: 1.6;
        color: var(--marca-oscuro);
      }

      .rag-descripcion strong {
        display: block;
        font-size: 14px;
        margin-bottom: 4px;
      }

      .rag-titulo-seccion {
        font-size: 14px;
        font-weight: 800;
        color: var(--tinta);
      }

      .rag-sugerencias {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      .rag-sugerencias button {
        border: 1px solid var(--linea);
        background: var(--gris);
        color: var(--tinta);
        font-size: 12px;
        font-weight: 700;
        border-radius: 14px;
        padding: 10px 12px;
        line-height: 1.4;
        text-align: left;
      }

      .rag-sugerencias button:hover {
        border-color: var(--marca);
        background: var(--marca-suave);
      }

      .rag-chat-cabecera {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }

      .rag-nuevo {
        border: 0;
        background: transparent;
        color: var(--marca);
        font-size: 12px;
        font-weight: 800;
        padding: 6px;
      }

      .rag-conversacion {
        display: flex;
        flex-direction: column;
        gap: 12px;
        min-height: 110px;
      }

      .rag-mensaje {
        border-radius: 18px;
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-width: 96%;
        min-width: 0;
      }

      .rag-mensaje-usuario {
        align-self: flex-end;
        background: var(--marca-oscuro);
        color: #fff;
        max-width: 88%;
        border-bottom-right-radius: 6px;
      }

      .rag-mensaje-asistente {
        align-self: flex-start;
        background: var(--gris);
        color: var(--tinta);
        border-bottom-left-radius: 6px;
      }

      .rag-mensaje-cabecera {
        font-size: 11px;
        font-weight: 800;
        opacity: 0.8;
      }

      .rag-mensaje-texto {
        font-size: 13px;
        line-height: 1.7;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }

      .rag-mensaje-texto strong {
        font-weight: 800;
      }

      .rag-fuentes {
        border-top: 1px solid var(--linea);
        padding-top: 10px;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        font-size: 11px;
      }

      .rag-fuentes > strong {
        width: 100%;
      }

      .rag-fuente {
        display: inline-flex;
        border-radius: 999px;
        padding: 5px 8px;
        background: #fff;
        border: 1px solid var(--linea);
        color: var(--marca-oscuro);
        font-weight: 800;
      }

      .rag-modelo {
        color: var(--tenue);
        font-weight: 700;
      }

      .rag-fuente-nota {
        width: 100%;
        color: var(--tenue);
        line-height: 1.5;
      }

      .rag-formulario {
        display: flex;
        flex-direction: column;
        gap: 12px;
        background: #fff;
        border: 1px solid var(--linea);
        border-radius: 20px;
        padding: 14px;
      }

      .rag-formulario label {
        font-size: 13px;
        font-weight: 800;
      }

      .rag-pregunta {
        width: 100%;
        min-height: 110px;
        max-height: 230px;
        resize: vertical;
        padding: 12px;
        border-radius: 14px;
        border: 1px solid var(--linea);
        background: var(--gris);
        color: var(--tinta);
        font: inherit;
        font-size: 14px;
        line-height: 1.5;
      }

      .rag-pregunta:focus {
        outline: 2px solid var(--marca);
        outline-offset: 2px;
      }

      .rag-contador {
        text-align: right;
        font-size: 11px;
        color: var(--tenue);
      }

      .rag-autorizacion {
        background: var(--oro-suave);
        border-radius: 14px;
        padding: 12px;
        display: flex;
        align-items: flex-start;
        gap: 10px;
        cursor: pointer;
      }

      .rag-autorizacion input {
        width: 20px;
        min-width: 20px;
        height: 20px;
        min-height: 20px;
        margin: 1px 0 0;
        padding: 0;
        accent-color: var(--marca);
      }

      .rag-autorizacion span {
        font-size: 12px;
        font-weight: 600;
        line-height: 1.6;
      }

      .rag-acciones {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
      }

      .rag-acciones button {
        min-height: 46px;
        border-radius: 14px;
        padding: 10px;
        font-size: 12px;
        line-height: 1.4;
        font-weight: 800;
      }

      .rag-solo-contexto {
        color: var(--marca-oscuro);
        background: var(--marca-suave);
        border: 1px solid var(--linea);
      }

      .rag-enviar {
        background: var(--marca);
        color: #fff;
        border: 0;
      }

      .rag-acciones button:disabled {
        opacity: 0.5;
      }

      .rag-error {
        color: var(--gasto);
        font-weight: 700;
        font-size: 13px;
        line-height: 1.5;
      }

      .rag-error:empty {
        display: none;
      }

      .rag-estado {
        color: var(--tenue);
        font-size: 12px;
        font-weight: 700;
      }

      .rag-estado:empty {
        display: none;
      }

      .rag-panel-contexto {
        border: 1px solid var(--linea);
        border-radius: 18px;
        background: var(--gris);
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        font-size: 12px;
        line-height: 1.6;
      }

      .rag-panel-contexto h3 {
        margin: 0;
        font-size: 14px;
      }

      .rag-panel-contexto ul {
        margin: 0;
        padding-left: 18px;
      }

      .rag-contexto-fecha {
        font-size: 11px;
        color: var(--tenue);
      }

      .rag-detalles summary {
        cursor: pointer;
        font-weight: 800;
        color: var(--marca);
      }

      .rag-detalles pre {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        background: #fff;
        border: 1px solid var(--linea);
        border-radius: 12px;
        padding: 10px;
        margin: 8px 0 0;
        font-size: 11px;
        max-height: 340px;
        overflow-y: auto;
      }

      .rag-nota-final {
        border-top: 1px solid var(--linea);
        padding-top: 12px;
        font-size: 11px;
        color: var(--tenue);
        line-height: 1.6;
      }

      .rag-panel-contexto[hidden] {
        display: none;
      }

      @media (max-width: 360px) {
        .rag-acciones {
          grid-template-columns: 1fr;
        }
      }
    </style>

    ${banda('Asistente financiero', {
    subtitulo:
      'Inteligencia artificial con PostgreSQL, Fuseki y RAG'
  })}

    <section class="rag-contenido">
      <div class="rag-descripcion">
        <strong>Consulta tus finanzas con IA</strong>
        Puedo ayudarte a comprender tus gastos,
        saldos disponibles, presupuestos y metas.
        No realizo operaciones con tu dinero.
      </div>

      <div>
        <h2 class="rag-titulo-seccion">
          Preguntas sugeridas
        </h2>
      </div>

      <div
        id="rag-sugerencias"
        class="rag-sugerencias"
      ></div>

      <div class="rag-chat-cabecera">
        <h2 class="rag-titulo-seccion">
          Conversación
        </h2>

        <button
          type="button"
          class="rag-nuevo"
          id="rag-nuevo"
        >
          Nueva conversación
        </button>
      </div>

      <div
        id="rag-conversacion"
        class="rag-conversacion"
        role="log"
        aria-label="Conversación con el asistente"
        aria-live="polite"
        aria-relevant="additions text"
      ></div>

      <form
        id="rag-formulario"
        class="rag-formulario"
        novalidate
      >
        <label for="rag-pregunta">
          Escribe tu pregunta financiera
        </label>

        <textarea
          id="rag-pregunta"
          class="rag-pregunta"
          maxlength="400"
          placeholder="Por ejemplo: ¿Cuánto pagué de GMF este mes?"
          required
        ></textarea>

        <div
          id="rag-contador"
          class="rag-contador"
        >
          0 / 400 caracteres
        </div>

        <label class="rag-autorizacion">
          <input
            id="rag-consentimiento"
            type="checkbox"
          >

          <span>
            Autorizo enviar esta pregunta y su
            contexto financiero recuperado a Google
            Gemini para generar una respuesta.
            Entiendo que es un servicio externo.
          </span>
        </label>

        <div class="rag-acciones">
          <button
            type="button"
            class="rag-solo-contexto"
            id="rag-ver-contexto"
            disabled
          >
            Diagnóstico sin IA
          </button>

          <button
            type="submit"
            class="rag-enviar"
            id="rag-enviar"
            disabled
          >
            Preguntar a Gemini
          </button>
        </div>

        <p
          id="rag-estado"
          class="rag-estado"
          role="status"
          aria-live="polite"
        ></p>

        <p
          id="rag-error"
          class="rag-error"
          role="alert"
        ></p>
      </form>

      <section
        id="rag-panel-contexto"
        class="rag-panel-contexto"
        aria-label="Evidencia recuperada"
        hidden
      ></section>

      <p class="rag-nota-final">
        Cada pregunta se analiza por separado.
        Esta pantalla no guarda conversaciones en
        el dispositivo. Las respuestas de IA pueden
        contener errores: verifica los cálculos
        importantes con tus saldos de la PWA.
        Los datos offline pendientes de sincronizar
        no se incluyen en el análisis.
      </p>
    </section>
  `;

  const form = c.querySelector('#rag-formulario');
  const pregunta = c.querySelector('#rag-pregunta');
  const consentimiento = c.querySelector(
    '#rag-consentimiento'
  );

  const enviar = c.querySelector('#rag-enviar');
  const verContexto = c.querySelector(
    '#rag-ver-contexto'
  );

  const conversacion = c.querySelector(
    '#rag-conversacion'
  );

  const panelContexto = c.querySelector(
    '#rag-panel-contexto'
  );

  const error = c.querySelector('#rag-error');
  const estado = c.querySelector('#rag-estado');
  const contador = c.querySelector('#rag-contador');

  const nuevo = c.querySelector('#rag-nuevo');
  const sugerencias = c.querySelector(
    '#rag-sugerencias'
  );

  const sesionVigente = () => (
    c.isConnected &&
    tokenInicial !== null &&
    obtenerToken() === tokenInicial &&
    usuarioInicial > 0 &&
    Number(obtenerUsuario()?.id_usuario) ===
    usuarioInicial
  );


  // ------------------------------------
  // INICIAR CONVERSACIÓN
  // ------------------------------------

  function bienvenida() {
    conversacion.replaceChildren();

    crearMensaje(
      conversacion,
      'asistente',
      (
        '¡Hola! Puedo analizar la información ' +
        'financiera que recuperamos de tus cuentas. ' +
        '\n\n' +
        'Selecciona una pregunta sugerida o ' +
        'escribe la tuya para comenzar.'
      )
    );
  }

  bienvenida();


  // ------------------------------------
  // SUGERENCIAS
  // ------------------------------------

  for (const texto of SUGERENCIAS) {
    const boton = document.createElement('button');

    boton.type = 'button';
    boton.textContent = texto;

    boton.addEventListener('click', () => {
      if (ocupada) return;

      pregunta.value = texto;

      actualizarControles();

      pregunta.focus();
    });

    sugerencias.appendChild(boton);
  }


  // ------------------------------------
  // CONTROLES DE FORMULARIO
  // ------------------------------------

  function actualizarControles() {
    const cantidad = pregunta.value.length;

    contador.textContent = (
      `${cantidad} / 400 caracteres`
    );

    const valida = (
      pregunta.value.trim().length >= 5 &&
      cantidad <= 400
    );

    pregunta.disabled = ocupada;
    consentimiento.disabled = ocupada;

    verContexto.disabled = (
      ocupada || !valida
    );

    enviar.disabled = (
      ocupada ||
      !valida ||
      !consentimiento.checked
    );

    nuevo.disabled = ocupada;

    sugerencias.querySelectorAll('button')
      .forEach(boton => {
        boton.disabled = ocupada;
      });
  }


  pregunta.addEventListener(
    'input',
    () => {
      error.textContent = '';

      actualizarControles();
    }
  );

  consentimiento.addEventListener(
    'change',
    () => {
      error.textContent = '';

      actualizarControles();
    }
  );


  // ------------------------------------
  // CONSULTAR RAG
  // ------------------------------------

  async function consultar(modo) {
    if (ocupada || !sesionVigente()) return;

    const texto = pregunta.value.trim();

    if (
      texto.length < 5 ||
      texto.length > 400
    ) {
      error.textContent = (
        'Escribe una pregunta de 5 a 400 caracteres.'
      );

      return;
    }

    const conIA = modo === 'ia';

    if (
      conIA &&
      !consentimiento.checked
    ) {
      error.textContent = (
        'Debes autorizar el envío a Gemini ' +
        'para generar una respuesta.'
      );

      return;
    }

    panelContexto.hidden = true;
    panelContexto.replaceChildren();
    error.textContent = '';
    estado.textContent = (
      conIA
        ? 'Recuperando información y consultando Gemini…'
        : 'Comprobando las fuentes de datos…'
    );

    ocupada = true;
    controlador = new AbortController();

    actualizarControles();

    let mensajePendiente = null;

    if (conIA) {
      crearMensaje(
        conversacion,
        'usuario',
        texto
      );

      mensajePendiente = crearMensaje(
        conversacion,
        'asistente',
        'Consultando tus datos financieros…'
      );
    }

    try {
      if (!navigator.onLine) {
        throw new ErrorDeRed(
          'No tienes conexión. El asistente ' +
          'solo puede responder cuando el ' +
          'backend y Fuseki están disponibles.'
        );
      }

      if (conIA) {

        const respuesta = await preguntarRAG(
          texto,
          {
            autorizoEnvioIA: consentimiento.checked,
            signal: controlador.signal
          }
        );


        if (!sesionVigente()) return;

        if (
          typeof respuesta.respuesta !== 'string' ||
          !respuesta.respuesta.trim()
        ) {
          throw new Error(
            'El servidor no devolvió texto del asistente.'
          );
        }

        textoSeguro(
          mensajePendiente.cuerpo,
          respuesta.respuesta
        );

        agregarFuentes(
          mensajePendiente.articulo,
          respuesta
        );

        // No conservamos la autorización para
        // preguntas futuras.
        consentimiento.checked = false;
        pregunta.value = '';

        estado.textContent = (
          'Respuesta generada. ' +
          'Puedes realizar otra pregunta.'
        );

      } else {
        const contexto = await consultarContextoRAG(
          texto,
          {
            signal: controlador.signal
          }
        );

        if (!sesionVigente()) return;

        mostrarEvidencia(
          panelContexto,
          contexto
        );

        estado.textContent = (
          'Diagnóstico completado sin llamar a Gemini.'
        );
      }

    } catch (excepcion) {
      if (!sesionVigente()) return;

      if (mensajePendiente) {
        mensajePendiente.articulo.remove();
      }

      error.textContent = textoError(
        excepcion
      );

      estado.textContent = '';

    } finally {
      ocupada = false;
      controlador = null;

      if (sesionVigente()) {
        // Después de cada intento de generación
        // se solicita consentimiento nuevamente.
        if (conIA) {
          consentimiento.checked = false;
        }

        actualizarControles();
      }
    }
  }


  form.addEventListener(
    'submit',
    async evento => {
      evento.preventDefault();

      await consultar('ia');
    }
  );

  verContexto.addEventListener(
    'click',
    async () => {
      await consultar('contexto');
    }
  );


  // ------------------------------------
  // NUEVA CONVERSACIÓN
  // ------------------------------------

  nuevo.addEventListener(
    'click',
    () => {
      if (ocupada) return;

      pregunta.value = '';
      consentimiento.checked = false;

      error.textContent = '';
      estado.textContent = '';

      panelContexto.hidden = true;
      panelContexto.replaceChildren();

      bienvenida();
      actualizarControles();

      pregunta.focus();
    }
  );


  // ------------------------------------
  // ESTADO INICIAL
  // ------------------------------------

  actualizarControles();
}
