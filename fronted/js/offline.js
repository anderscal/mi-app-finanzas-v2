// Capa que usan las pantallas para el modo sin conexión.
// Por debajo usa offline-db.js y sync.js, los mismos módulos que
// probó el backend en backend/JS/, así las reglas son idénticas:
//  - cada operación conserva su UUID (el backend no la duplica);
//  - la cola es por usuario;
//  - se envía en orden y se detiene en la primera operación rechazada,
//    porque las siguientes pueden depender de ella.

import {
  guardarOperacionPendiente,
  obtenerOperacionesLocales,
  actualizarOperacionLocal,
  eliminarOperacion,
} from './offline-db.js';
import { sincronizarPendientes } from './sync.js';
import { obtenerToken, obtenerUsuario } from './sesion.js';

export const TIPOS_OPERACION = {
  MOVIMIENTO_NORMAL: 'Ingreso o gasto',
  TRANSFERENCIA: 'Transferencia',
  ABONO_OBLIGACION: 'Pago o cobro de obligación',
};

function usuarioActual() {
  return obtenerUsuario()?.id_usuario ?? null;
}

// Guarda una operación para enviarla después.
// tipo: MOVIMIENTO_NORMAL | TRANSFERENCIA | ABONO_OBLIGACION
// datos: el mismo cuerpo JSON que se enviaría al endpoint.
export async function guardarOffline(tipo, uuid, datos) {
  const usuarioId = usuarioActual();
  if (!usuarioId) throw new Error('Inicia sesión para guardar sin conexión.');

  const existente = (await obtenerOperacionesLocales()).find((op) => op.uuid_operacion === uuid);
  if (existente) {
    // Nunca sobrescribir una operación guardada con datos distintos.
    if (existente.usuario_id !== usuarioId || existente.tipo_operacion !== tipo
        || JSON.stringify(existente.datos) !== JSON.stringify(datos)) {
      throw new Error('Esta operación ya estaba guardada con otros datos.');
    }
    return;
  }
  await guardarOperacionPendiente({ uuid_operacion: uuid, usuario_id: usuarioId, tipo_operacion: tipo, datos });
}

// Operaciones locales del usuario actual, en el orden en que se enviarán.
export async function operacionesLocales() {
  const usuarioId = usuarioActual();
  try {
    return (await obtenerOperacionesLocales())
      .filter((op) => op.usuario_id === usuarioId)
      .sort((a, b) => a.fecha_local.localeCompare(b.fecha_local));
  } catch {
    return [];
  }
}

// Vuelve a poner en cola una operación rechazada, con el mismo UUID y datos.
export function reintentarOperacion(uuid) {
  return actualizarOperacionLocal(uuid, { estado_sync: 'PENDIENTE', ultimo_error: null });
}

// Borra solo la copia local. No anula nada en el servidor.
export function descartarOperacion(uuid) {
  return eliminarOperacion(uuid);
}

// Un 422 son datos inválidos: reenviarlos igual no sirve.
export function esErrorDeDatos(op) {
  return String(op.ultimo_error || '').startsWith('HTTP 422');
}

let mensajes = [];

// Devuelve { sincronizadas, pendientes, errores, mensajes } o null si no se pudo intentar.
export async function sincronizar() {
  const token = obtenerToken();
  const usuarioId = usuarioActual();
  if (!token || !usuarioId || !navigator.onLine) return null;
  mensajes = [];
  try {
    const resumen = await sincronizarPendientes({ token, usuarioId, onEvento: (m) => mensajes.push(m) });
    return resumen ? { ...resumen, mensajes } : null;
  } catch {
    return null;
  }
}
