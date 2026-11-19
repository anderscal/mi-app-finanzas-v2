
import {
  guardarOperacionPendiente,
  obtenerOperacionesLocales,
  actualizarOperacionLocal,
  eliminarOperacion
} from './offline-db.js';

import {
  sincronizarPendientes
} from './sync.js';

import {
  obtenerToken,
  obtenerUsuario
} from './sesion.js';


export const TIPOS_OPERACION = {
  MOVIMIENTO_NORMAL: 'Ingreso o gasto',
  TRANSFERENCIA: 'Transferencia',
  ABONO_OBLIGACION: 'Pago o cobro de obligación'
};

// Bloqueo compartido entre pestañas del mismo origen.
const NOMBRE_BLOQUEO = 'fp-cola-financiera-v1';


function usuarioActual() {
  const id = Number(
    obtenerUsuario()?.id_usuario
  );

  return Number.isSafeInteger(id) && id > 0
    ? id
    : null;
}


function verificarBloqueoDisponible() {
  if (
    !navigator.locks ||
    typeof navigator.locks.request !== 'function'
  ) {
    throw new Error(
      'Este navegador no dispone del bloqueo ' +
      'seguro entre pestañas. Las operaciones ' +
      'se conservarán en el dispositivo.'
    );
  }
}


// Evita que dos pestañas sincronicen o modifiquen
// simultáneamente las mismas operaciones.
async function conBloqueo(accion) {
  verificarBloqueoDisponible();

  return navigator.locks.request(
    NOMBRE_BLOQUEO,
    { mode: 'exclusive' },
    accion
  );
}


function esLaMismaOperacion(existente, usuarioId, tipo, datos) {
  return (
    Number(existente.usuario_id) === usuarioId &&
    existente.tipo_operacion === tipo &&
    JSON.stringify(existente.datos) ===
      JSON.stringify(datos)
  );
}


// ------------------------------------
// GUARDAR OPERACION EN INDEXEDDB
// ------------------------------------

export async function guardarOffline(
  tipo,
  uuid,
  datos
) {
  const usuarioId = usuarioActual();

  if (!usuarioId) {
    throw new Error(
      'Inicia sesión para guardar operaciones.'
    );
  }

  if (!TIPOS_OPERACION[tipo]) {
    throw new Error(
      'Tipo de operación no válido.'
    );
  }

  if (!uuid || !datos) {
    throw new Error(
      'La operación no tiene UUID o datos.'
    );
  }

  const operaciones =
    await obtenerOperacionesLocales();

  const existente = operaciones.find(
    op => op.uuid_operacion === uuid
  );

  if (existente) {
    if (!esLaMismaOperacion(
      existente,
      usuarioId,
      tipo,
      datos
    )) {
      throw new Error(
        'El UUID ya corresponde a otros datos.'
      );
    }

    return;
  }

  try {
    await guardarOperacionPendiente({
      uuid_operacion: uuid,
      usuario_id: usuarioId,
      tipo_operacion: tipo,
      datos
    });

  } catch (error) {
    // Si dos pestañas intentan guardar el mismo
    // UUID, IndexedDB tiene una clave única.
    // Comprobamos si ambas solicitudes eran
    // realmente idénticas.
    const actual = (
      await obtenerOperacionesLocales()
    ).find(op => op.uuid_operacion === uuid);

    if (
      actual &&
      esLaMismaOperacion(
        actual,
        usuarioId,
        tipo,
        datos
      )
    ) {
      return;
    }

    throw error;
  }
}


// ------------------------------------
// MOSTRAR OPERACIONES DEL USUARIO
// ------------------------------------

export async function operacionesLocales() {
  const usuarioId = usuarioActual();

  if (!usuarioId) return [];

  try {
    return (
      await obtenerOperacionesLocales()
    )
      .filter(
        op => Number(op.usuario_id) === usuarioId
      )
      .sort(
        (a, b) =>
          String(a.fecha_local).localeCompare(
            String(b.fecha_local)
          )
      );

  } catch (error) {
    console.warn(
      'No se pudo consultar la cola local:',
      error
    );

    return [];
  }
}


// ------------------------------------
// VALIDAR PROPIEDAD LOCAL
// ------------------------------------

async function verificarOperacionPropia(uuid, usuarioId) {
  const operacion = (
    await obtenerOperacionesLocales()
  ).find(op => op.uuid_operacion === uuid);

  if (
    !operacion ||
    Number(operacion.usuario_id) !== usuarioId ||
    usuarioActual() !== usuarioId
  ) {
    throw new Error(
      'Operación no encontrada para este usuario.'
    );
  }

  return operacion;
}


// ------------------------------------
// REINTENTAR OPERACION RECHAZADA
// ------------------------------------

export function reintentarOperacion(uuid) {
  return conBloqueo(async () => {
    const id = usuarioActual();

    if (!id) {
      throw new Error('Debes iniciar sesión.');
    }

    await verificarOperacionPropia(uuid, id);

    return actualizarOperacionLocal(uuid, {
      estado_sync: 'PENDIENTE',
      ultimo_error: null
    });
  });
}


// ------------------------------------
// DESCARTAR SOLO LA COPIA LOCAL
// ------------------------------------

export function descartarOperacion(uuid) {
  return conBloqueo(async () => {
    const id = usuarioActual();

    if (!id) {
      throw new Error('Debes iniciar sesión.');
    }

    await verificarOperacionPropia(uuid, id);

    return eliminarOperacion(uuid);
  });
}


export function esErrorDeDatos(op) {
  return String(
    op.ultimo_error || ''
  ).startsWith('HTTP 422');
}


// ------------------------------------
// SINCRONIZAR CON BLOQUEO COMPARTIDO
// ------------------------------------

export async function sincronizar() {
  const token = obtenerToken();
  const usuarioId = usuarioActual();

  if (
    !token ||
    !usuarioId ||
    !navigator.onLine
  ) {
    return null;
  }

  const sesionVigente = () => (
    obtenerToken() === token &&
    usuarioActual() === usuarioId
  );

  try {
    return await conBloqueo(async () => {

      // Otra pestaña pudo cerrar sesión
      // mientras esperábamos el bloqueo.
      if (
        !sesionVigente() ||
        !navigator.onLine
      ) {
        return null;
      }

      const mensajes = [];

      const resumen = await sincronizarPendientes({
        token,
        usuarioId,
        sesionVigente,
        onEvento: mensaje => {
          mensajes.push(mensaje);
        }
      });

      return resumen
        ? { ...resumen, mensajes }
        : null;
    });

  } catch (error) {
    console.warn(
      'No se pudo sincronizar de forma segura:',
      error
    );

    return null;
  }
}
