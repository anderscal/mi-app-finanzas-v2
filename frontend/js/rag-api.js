
/**
 * Cliente de la API RAG.
 *
 * Solo realiza consultas autenticadas a FastAPI.
 * No envía credenciales a Gemini.
 * No utiliza IndexedDB ni la cola offline.
 */

import { CONFIG } from './config.js';

import {
  obtenerToken,
  cerrarSesion
} from './sesion.js';

import {
  ErrorApi,
  ErrorDeRed
} from './api.js';


function mensajeDeError(datos, estado) {
  const detalle = datos?.detail;

  if (typeof detalle === 'string') {
    return detalle;
  }

  if (Array.isArray(detalle) && detalle.length) {
    return detalle.map(error => {
      const ubicacion = Array.isArray(error.loc)
        ? error.loc[error.loc.length - 1]
        : '';

      const mensaje = String(
        error.msg || 'Dato inválido'
      ).replace(/^Value error, /, '');

      return ubicacion && ubicacion !== 'body'
        ? `${ubicacion}: ${mensaje}`
        : mensaje;
    }).join(' · ');
  }

  return `Error HTTP ${estado}`;
}


async function solicitarRAG(
  ruta,
  datos,
  { signal } = {}
) {
  const token = obtenerToken();

  if (!token) {
    location.hash = '#/login';

    throw new ErrorApi(
      401,
      'Tu sesión ha vencido. Inicia sesión nuevamente.'
    );
  }

  if (!navigator.onLine) {
    throw new ErrorDeRed(
      'No hay conexión. El asistente RAG ' +
      'necesita comunicarse con FastAPI y Fuseki.'
    );
  }

  let respuesta;

  try {
    respuesta = await fetch(
      CONFIG.API_URL + ruta,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(datos),
        cache: 'no-store',
        signal
      }
    );

  } catch (error) {
    if (error?.name === 'AbortError') {
      throw error;
    }

    throw new ErrorDeRed(
      'No fue posible conectar con FastAPI. ' +
      'Verifica que el backend esté funcionando.'
    );
  }

  let contenido = null;

  try {
    contenido = await respuesta.json();
  } catch {
    // La respuesta podría no contener JSON.
  }

  if (obtenerToken() !== token) {
    if (!obtenerToken()) location.hash = '#/login';
    throw new ErrorApi(401, 'La sesión cambió durante la solicitud.');
  }

  if (!respuesta.ok) {
    if (respuesta.status === 401) {
      cerrarSesion();
      location.hash = '#/login';
    }

    throw new ErrorApi(
      respuesta.status,
      mensajeDeError(
        contenido,
        respuesta.status
      )
    );
  }

  if (!contenido || typeof contenido !== 'object') {
    throw new ErrorApi(
      502,
      'FastAPI devolvió una respuesta RAG inválida.'
    );
  }

  return contenido;
}


/**
 * Recupera evidencia sin llamar a Gemini.
 *
 * POST /consultas/asistente/contexto
 */
export function consultarContextoRAG(
  pregunta,
  opciones = {}
) {
  return solicitarRAG(
    '/consultas/asistente/contexto',
    {
      pregunta: String(pregunta).trim()
    },
    opciones
  );
}


/**
 * Recupera contexto y genera respuesta con Gemini.
 *
 * POST /consultas/asistente/preguntar
 *
 * El consentimiento se recoge en la interfaz,
 * pero también lo comprueba el backend.
 */

export function preguntarRAG(
  pregunta,
  { autorizoEnvioIA = false, ...opciones } = {}
) {
  if (autorizoEnvioIA !== true) {
    throw new ErrorApi(
      403,
      'Debes autorizar el envío de contexto financiero a Gemini.'
    );
  }

  return solicitarRAG(
    '/consultas/asistente/preguntar',
    {
      pregunta: String(pregunta).trim(),
      autorizo_envio_ia: true
    },
    opciones
  );
}

