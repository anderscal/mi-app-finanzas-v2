
import {
  obtenerSaldosReservados,
  ErrorDeRed
} from './api.js';

import {
  guardarCache,
  leerCache
} from './util.js';

import { obtenerUsuario } from './sesion.js';

const CLAVE = 'metas-saldos-reservados';

export async function consultarReservasVisibles() {
  const idUsuario = Number(
    obtenerUsuario()?.id_usuario
  );

  const mismaSesion = () =>
    Number.isSafeInteger(idUsuario) &&
    idUsuario > 0 &&
    Number(obtenerUsuario()?.id_usuario) === idUsuario;

  if (!mismaSesion()) {
    throw new Error('La sesión no está disponible.');
  }

  try {
    const datos = await obtenerSaldosReservados();

    if (!mismaSesion()) {
      throw new Error(
        'La sesión cambió durante la consulta.'
      );
    }

    if (!Array.isArray(datos)) {
      throw new Error(
        'El servidor devolvió saldos de reservas inválidos.'
      );
    }

    guardarCache(CLAVE, datos);

    return {
      datos,
      desdeCache: false,
      fecha: Date.now()
    };

  } catch (error) {
    if (
      error instanceof ErrorDeRed &&
      mismaSesion()
    ) {
      const cache = leerCache(CLAVE);

      if (Array.isArray(cache?.datos)) {
        return {
          datos: cache.datos,
          desdeCache: true,
          fecha: cache.en || null
        };
      }
    }

    throw error;
  }
}


export function encontrarSaldoReserva(
  consulta,
  idCuenta
) {
  if (
    !consulta ||
    !Array.isArray(consulta.datos)
  ) {
    return null;
  }

  return consulta.datos.find(
    item =>
      Number(item.id_cuenta) === Number(idCuenta)
  ) || null;
}


export function textoEstadoSaldo(consulta) {
  if (!consulta) {
    return (
      'Saldo libre no disponible: ' +
      'el servidor verificará la operación.'
    );
  }

  if (!consulta.desdeCache) {
    return (
      'Saldos consultados; ' +
      'el servidor validará al guardar.'
    );
  }

  const hora = consulta.fecha
    ? new Date(consulta.fecha).toLocaleString(
        'es-CO',
        {
          day: 'numeric',
          month: 'short',
          hour: '2-digit',
          minute: '2-digit'
        }
      )
    : 'la última consulta';

  return (
    `Dato guardado (${hora}). ` +
    'Puede haber cambiado; ' +
    'se verificará al sincronizar.'
  );
}
