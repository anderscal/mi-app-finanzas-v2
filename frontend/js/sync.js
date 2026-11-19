
import {
  obtenerOperacionesLocales,
  actualizarOperacionLocal,
  eliminarOperacion
} from './offline-db.js';

import { CONFIG } from './config.js';


export const API_URL = CONFIG.API_URL;

const RUTAS = {
  MOVIMIENTO_NORMAL: '/movimientos/normales',
  TRANSFERENCIA: '/transferencias/',
  ABONO_OBLIGACION: '/obligaciones/abonos'
};

// Una espera demasiado larga no debe
// mantener bloqueada la cola indefinidamente.
const TIMEOUT_MS = 25000;

let sincronizando = false;


function describirErrorHTTP(cuerpo) {
  const detalle = cuerpo?.detail;

  if (typeof detalle === 'string') {
    return detalle;
  }

  if (Array.isArray(detalle)) {
    return detalle.map(error => {
      const campo = Array.isArray(error.loc)
        ? error.loc.join('.')
        : 'datos';

      return (
        `${campo}: ${error.msg || 'Valor inválido'}`
      );
    }).join(' | ');
  }

  return 'La operación fue rechazada';
}


function esUUIDConfirmado(valor, esperado) {
  return (
    typeof valor === 'string' &&
    valor.toLowerCase() ===
      String(esperado).toLowerCase()
  );
}


function confirmarRespuesta(operacion, cuerpo) {
  if (typeof cuerpo?.creado !== 'boolean') {
    return false;
  }

  if (operacion.tipo_operacion === 'TRANSFERENCIA') {
    const id = Number(cuerpo.id_transferencia);

    return (
      Number.isSafeInteger(id) &&
      id > 0 &&
      esUUIDConfirmado(
        cuerpo.uuid_operacion,
        operacion.uuid_operacion
      )
    );
  }

  return esUUIDConfirmado(
    cuerpo.uuid_local,
    operacion.uuid_operacion
  );
}


// ---------------------------------------
// SINCRONIZADOR DE OPERACIONES PENDIENTES
// ---------------------------------------

export async function sincronizarPendientes({
  token,
  usuarioId,
  onEvento = () => {},
  sesionVigente = () => true
}) {

  const idUsuario = Number(usuarioId);

  if (
    !token ||
    !Number.isSafeInteger(idUsuario) ||
    idUsuario <= 0
  ) {
    throw new Error(
      'Debes iniciar sesión antes de sincronizar.'
    );
  }

  if (sincronizando) {
    onEvento('Ya existe una sincronización en curso.');
    return null;
  }

  sincronizando = true;

  const resumen = {
    sincronizadas: 0,
    pendientes: 0,
    errores: 0,
    sesionCambiada: false
  };


  function comprobarSesion() {
    if (sesionVigente()) {
      return true;
    }

    resumen.sesionCambiada = true;

    onEvento(
      'La sesión cambió durante la sincronización. ' +
      'Las operaciones restantes se conservarán.'
    );

    return false;
  }


  try {
    // -----------------------------------
    // 1. CARGAR LA COLA DEL USUARIO
    // -----------------------------------

    if (!comprobarSesion()) {
      return resumen;
    }

    const todas = await obtenerOperacionesLocales();

    const operaciones = todas
      .filter(op =>
        Number(op.usuario_id) === idUsuario &&
        Boolean(RUTAS[op.tipo_operacion]) &&
        ['PENDIENTE', 'ERROR'].includes(
          op.estado_sync
        )
      )
      .sort((a, b) =>
        String(a.fecha_local).localeCompare(
          String(b.fecha_local)
        )
      );


    // -----------------------------------
    // 2. PROCESAR EN ORDEN
    // -----------------------------------

    for (const operacion of operaciones) {

      if (!comprobarSesion()) {
        resumen.pendientes++;
        break;
      }

      // Un error previo bloquea la cola:
      // las siguientes operaciones pueden
      // depender de esta.
      if (operacion.estado_sync === 'ERROR') {

        resumen.errores++;

        onEvento(
          'Sincronización detenida: existe una ' +
          'operación rechazada que requiere revisión. ' +
          'UUID: ' + operacion.uuid_operacion
        );

        break;
      }

      const uuid = operacion.uuid_operacion;

      await actualizarOperacionLocal(uuid, {
        intentos: (operacion.intentos || 0) + 1,
        ultimo_error: null
      });

      // La sesión pudo cambiar durante
      // la escritura anterior en IndexedDB.
      if (!comprobarSesion()) {
        resumen.pendientes++;
        break;
      }

      // ---------------------------------
      // 3. ENVIAR A FASTAPI
      // ---------------------------------

      const controlador = new AbortController();

      const temporizador = setTimeout(
        () => controlador.abort(),
        TIMEOUT_MS
      );

      let respuesta;

      try {
        respuesta = await fetch(
          API_URL + RUTAS[operacion.tipo_operacion],
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`
            },
            body: JSON.stringify(operacion.datos),
            signal: controlador.signal
          }
        );

      } catch (error) {
        clearTimeout(temporizador);

        if (!comprobarSesion()) {
          resumen.pendientes++;
          break;
        }

        // Un error de red o timeout NO demuestra
        // que PostgreSQL rechazara la operación.
        // Se conserva el UUID original.
        await actualizarOperacionLocal(uuid, {
          estado_sync: 'PENDIENTE',
          ultimo_error:
            'Sin conexión o confirmación no recibida'
        });

        resumen.pendientes++;

        onEvento(
          'No se recibió confirmación. ' +
          'La operación sigue pendiente.'
        );

        break;

      } finally {
        clearTimeout(temporizador);
      }


      // ---------------------------------
      // 4. LEER RESPUESTA
      // ---------------------------------

      let cuerpo = {};

      try {
        cuerpo = await respuesta.json();
      } catch {
        // Respuesta vacía o no válida.
      }

      if (!comprobarSesion()) {
        // Puede que el servidor ya haya procesado
        // la solicitud, pero no borramos el registro
        // mientras la sesión ha cambiado.
        resumen.pendientes++;
        break;
      }


      // ---------------------------------
      // 5. CONFIRMACION VERIFICABLE
      // ---------------------------------

      if (respuesta.ok) {

        if (!confirmarRespuesta(operacion, cuerpo)) {

          await actualizarOperacionLocal(uuid, {
            estado_sync: 'PENDIENTE',
            ultimo_error:
              'El servidor respondió, pero no fue ' +
              'posible confirmar la operación.'
          });

          resumen.pendientes++;

          onEvento(
            'Confirmación no verificable. ' +
            'Se conservará el mismo UUID.'
          );

          break;
        }

        // El backend confirmó el UUID correcto.
        await eliminarOperacion(uuid);

        resumen.sincronizadas++;

        onEvento(
          cuerpo.creado
            ? 'Operación registrada en PostgreSQL.'
            : 'Operación existente reconocida por UUID.'
        );

        continue;
      }


      // ---------------------------------
      // 6. SESION EXPIRADA
      // ---------------------------------

      if (respuesta.status === 401) {

        await actualizarOperacionLocal(uuid, {
          estado_sync: 'PENDIENTE',
          ultimo_error:
            'Sesión expirada. Inicia sesión nuevamente.'
        });

        resumen.pendientes++;

        onEvento('La sesión expiró.');

        break;
      }


      // ---------------------------------
      // 7. RECHAZOS DE NEGOCIO
      // ---------------------------------

      if ([400, 403, 404, 409, 422].includes(
        respuesta.status
      )) {

        await actualizarOperacionLocal(uuid, {
          estado_sync: 'ERROR',
          ultimo_error:
            `HTTP ${respuesta.status}: ` +
            describirErrorHTTP(cuerpo)
        });

        resumen.errores++;

        onEvento(
          `Operación rechazada: HTTP ${respuesta.status}`
        );

        // Detenerse antes de procesar la siguiente.
        break;
      }


      // ---------------------------------
      // 8. FALLOS TRANSITORIOS
      // ---------------------------------

      await actualizarOperacionLocal(uuid, {
        estado_sync: 'PENDIENTE',
        ultimo_error:
          `HTTP ${respuesta.status}: reintentar`
      });

      resumen.pendientes++;

      onEvento(
        'El servidor no pudo completar la operación.'
      );

      break;
    }

    return resumen;

  } finally {
    sincronizando = false;
  }
}
