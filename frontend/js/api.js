// Una función por endpoint del backend FastAPI.
// Si el backend cambia una ruta o un campo, se ajusta aquí y en ningún otro lugar.

// API centralizada de la PWA Finanzas Personales.

import { CONFIG } from './config.js';

import {
  obtenerToken,
  cerrarSesion
} from './sesion.js';


export class ErrorApi extends Error {
  constructor(estado, mensaje) {
    super(mensaje);
    this.estado = estado;
  }
}


export class ErrorDeRed extends Error {}


function mensajeDeError(cuerpo, estado) {
  const detalle = cuerpo?.detail;

  if (typeof detalle === 'string') {
    return detalle;
  }

  if (Array.isArray(detalle) && detalle.length) {
    return detalle.map(error => {
      const campo = Array.isArray(error.loc)
        ? error.loc[error.loc.length - 1]
        : '';

      const mensaje = String(
        error.msg || 'Dato inválido'
      ).replace(/^Value error, /, '');

      return campo && campo !== 'body'
        ? `${campo}: ${mensaje}`
        : mensaje;
    }).join(' · ');
  }

  return `El servidor respondió con error ${estado}`;
}


async function solicitar(
  ruta,
  {
    metodo = 'GET',
    json,
    formulario,
    conToken = true
  } = {}
) {
  const encabezados = {};
  let cuerpo;

  if (json !== undefined) {
    encabezados['Content-Type'] = 'application/json';
    cuerpo = JSON.stringify(json);

  } else if (formulario !== undefined) {
    encabezados['Content-Type'] =
      'application/x-www-form-urlencoded';

    cuerpo = new URLSearchParams(
      formulario
    ).toString();
  }

  if (conToken) {
    const token = obtenerToken();

    if (!token) {
      location.hash = '#/login';

      throw new ErrorApi(
        401,
        'Tu sesión venció. Vuelve a iniciar sesión.'
      );
    }

    encabezados.Authorization = `Bearer ${token}`;
  }

  let respuesta;

  try {
    respuesta = await fetch(
      CONFIG.API_URL + ruta,
      {
        method: metodo,
        headers: encabezados,
        body: cuerpo
      }
    );

  } catch {
    throw new ErrorDeRed(
      'No hay conexión con el servidor.'
    );
  }

  let datos = null;

  try {
    datos = await respuesta.json();
  } catch {
    // Algunas respuestas no tienen cuerpo JSON.
  }

  if (!respuesta.ok) {
    if (respuesta.status === 401 && conToken) {
      cerrarSesion();
      location.hash = '#/login';
    }

    throw new ErrorApi(
      respuesta.status,
      mensajeDeError(datos, respuesta.status)
    );
  }

  return datos;
}


// -----------------------------------
// AUTENTICACIÓN
// -----------------------------------

export function registrarUsuario({
  nombre_1,
  nombre_2,
  apellido_1,
  apellido_2,
  email,
  password
}) {
  return solicitar('/auth/registro', {
    metodo: 'POST',
    conToken: false,
    json: {
      nombre_1,
      nombre_2: nombre_2 || null,
      apellido_1,
      apellido_2: apellido_2 || null,
      email,
      password
    }
  });
}


export function iniciarSesion(email, password) {
  return solicitar('/auth/login', {
    metodo: 'POST',
    conToken: false,
    formulario: {
      username: email,
      password
    }
  });
}


export function obtenerPerfil() {
  return solicitar('/auth/me');
}


// -----------------------------------
// CUENTAS FINANCIERAS
// -----------------------------------

export function obtenerMisCuentas() {
  return solicitar('/auth/mis-cuentas');
}


export function crearCuentaFinanciera(datos) {
  return solicitar('/cuentas/', {
    metodo: 'POST',
    json: datos
  });
}


export function actualizarCuentaFinanciera(
  idCuenta,
  datos
) {
  return solicitar(`/cuentas/${idCuenta}`, {
    metodo: 'PATCH',
    json: datos
  });
}


export function desactivarCuentaFinanciera(idCuenta) {
  return solicitar(
    `/cuentas/${idCuenta}/desactivar`,
    {
      metodo: 'POST'
    }
  );
}


// -----------------------------------
// MOVIMIENTOS
// -----------------------------------

export function crearMovimientoNormal(datos) {
  return solicitar('/movimientos/normales', {
    metodo: 'POST',
    json: datos
  });
}


export function anularMovimiento(idMovimiento) {
  return solicitar(
    `/movimientos/${idMovimiento}/anular`,
    {
      metodo: 'POST'
    }
  );
}


// -----------------------------------
// TRANSFERENCIAS
// -----------------------------------

export function crearTransferencia({
  uuid_operacion,
  id_cuenta_origen,
  id_cuenta_destino,
  monto,
  fecha_transferencia,
  motivo,
  aplica_gmf
}) {
  const datos = {
    uuid_operacion,
    id_cuenta_origen,
    id_cuenta_destino,
    monto,
    fecha_transferencia,
    aplica_gmf
  };

  if (motivo) {
    datos.motivo = motivo;
  }

  return solicitar('/transferencias/', {
    metodo: 'POST',
    json: datos
  });
}


// -----------------------------------
// OBLIGACIONES FINANCIERAS
// -----------------------------------

// Crear deuda o préstamo.
export function crearObligacion(datos) {
  return solicitar('/obligaciones/', {
    metodo: 'POST',
    json: datos
  });
}


// Consultar todos los datos de una obligación.
export function obtenerObligacion(idObligacion) {
  return solicitar(`/obligaciones/${idObligacion}`);
}


// Editar nombre, vencimiento y descripción.
export function actualizarObligacion(
  idObligacion,
  datos
) {
  return solicitar(
    `/obligaciones/${idObligacion}`,
    {
      metodo: 'PATCH',
      json: datos
    }
  );
}


// Desactivar sin eliminar el registro.
export function desactivarObligacion(idObligacion) {
  return solicitar(
    `/obligaciones/${idObligacion}/desactivar`,
    {
      metodo: 'POST'
    }
  );
}


// Abonar a una deuda o cobrar un préstamo.
export function registrarAbono({
  uuid_local,
  id_cuenta,
  id_obligacion,
  monto,
  fecha_movimiento,
  descripcion
}) {
  return solicitar('/obligaciones/abonos', {
    metodo: 'POST',
    json: {
      uuid_local,
      id_cuenta,
      id_obligacion,
      monto,
      fecha_movimiento,
      descripcion: descripcion || null
    }
  });
}


// -----------------------------------
// CONSULTAS FINANCIERAS
// -----------------------------------

export function obtenerResumenMensual(anio, mes) {
  return solicitar(
    `/consultas/resumen-mensual?anio=${anio}&mes=${mes}`
  );
}


export function obtenerHistorialMensual(anio, mes) {
  return solicitar(
    `/consultas/historial-mensual?anio=${anio}&mes=${mes}`
  );
}


export function obtenerPlanificacion() {
  return solicitar('/consultas/planificacion');
}


// -----------------------------------
// CATEGORÍAS
// -----------------------------------

export function obtenerCategorias() {
  return solicitar('/categorias/');
}


export function crearCategoriaFinanciera(datos) {
  return solicitar('/categorias/', {
    metodo: 'POST',
    json: datos
  });
}


export function actualizarCategoriaFinanciera(
  idCategoria,
  datos
) {
  return solicitar(`/categorias/${idCategoria}`, {
    metodo: 'PATCH',
    json: datos
  });
}


export function desactivarCategoriaFinanciera(idCategoria) {
  return solicitar(
    `/categorias/${idCategoria}/desactivar`,
    {
      metodo: 'POST'
    }
  );
}
