// Una función por endpoint del backend FastAPI.
// Si el backend cambia una ruta o un campo, se ajusta aquí y en ningún otro lugar.

// API centralizada de la PWA Finanzas Personales.

import { CONFIG } from './config.js';
import { obtenerToken, cerrarSesion } from './sesion.js';

export class ErrorApi extends Error {
  constructor(estado, mensaje) {
    super(mensaje);
    this.estado = estado;
  }
}

export class ErrorDeRed extends Error {}

function mensajeDeError(cuerpo, estado) {
  const detalle = cuerpo?.detail;

  if (typeof detalle === 'string') return detalle;

  if (Array.isArray(detalle) && detalle.length) {
    return detalle.map(e => {
      const campo = Array.isArray(e.loc)
        ? e.loc[e.loc.length - 1]
        : '';

      const mensaje = String(
        e.msg || 'Dato inválido'
      ).replace(/^Value error, /, '');

      return campo && campo !== 'body'
        ? `${campo}: ${mensaje}`
        : mensaje;
    }).join(' · ');
  }

  return `Error del servidor: ${estado}`;
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
  const headers = {};
  let body;
  let token = null;

  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);

  } else if (formulario !== undefined) {
    headers['Content-Type'] =
      'application/x-www-form-urlencoded';

    body = new URLSearchParams(formulario).toString();
  }

  if (conToken) {
    token = obtenerToken();

    if (!token) {
      location.hash = '#/login';

      throw new ErrorApi(
        401,
        'Tu sesión venció. Inicia sesión nuevamente.'
      );
    }

    headers.Authorization = `Bearer ${token}`;
  }

  let respuesta;

  try {
    respuesta = await fetch(
      CONFIG.API_URL + ruta,
      {
        method: metodo,
        headers,
        body,
        cache: 'no-store'
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
    // Respuesta sin JSON.
  }

  if (conToken && obtenerToken() !== token) {
    if (!obtenerToken()) location.hash = '#/login';
    throw new ErrorApi(401, 'La sesión cambió durante la solicitud.');
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


// AUTENTICACIÓN

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

export function solicitarRecuperacion(email) {

  return solicitar('/auth/solicitar-recuperacion', {
    metodo: 'POST',
    conToken: false,
    json: { email }
  });
}


export function restablecerContrasena(datos) {

  return solicitar('/auth/restablecer-contrasena', {
    metodo: 'POST',
    conToken: false,
    json: datos
  });
}


export function cambiarContrasena(datos) {

  return solicitar('/auth/cambiar-contrasena', {
    metodo: 'POST',
    json: datos
  });
}


export function obtenerPerfil() {
  return solicitar('/auth/me');
}


// CUENTAS

export function obtenerMisCuentas() {
  return solicitar('/auth/mis-cuentas');
}

export function crearCuentaFinanciera(datos) {
  return solicitar('/cuentas/', {
    metodo: 'POST',
    json: datos
  });
}

export function actualizarCuentaFinanciera(id, datos) {
  return solicitar(`/cuentas/${id}`, {
    metodo: 'PATCH',
    json: datos
  });
}

export function desactivarCuentaFinanciera(id) {
  return solicitar(
    `/cuentas/${id}/desactivar`,
    { metodo: 'POST' }
  );
}


// MOVIMIENTOS

export function crearMovimientoNormal(datos) {
  return solicitar('/movimientos/normales', {
    metodo: 'POST',
    json: datos
  });
}

export function anularMovimiento(id) {
  return solicitar(
    `/movimientos/${id}/anular`,
    { metodo: 'POST' }
  );
}


// TRANSFERENCIAS

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


// OBLIGACIONES

export function crearObligacion(datos) {
  return solicitar('/obligaciones/', {
    metodo: 'POST',
    json: datos
  });
}

export function obtenerObligacion(id) {
  return solicitar(`/obligaciones/${id}`);
}

export function actualizarObligacion(id, datos) {
  return solicitar(`/obligaciones/${id}`, {
    metodo: 'PATCH',
    json: datos
  });
}

export function desactivarObligacion(id) {
  return solicitar(
    `/obligaciones/${id}/desactivar`,
    { metodo: 'POST' }
  );
}

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


// CONSULTAS

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


// CATEGORÍAS

export function obtenerCategorias() {
  return solicitar('/categorias/');
}

export function crearCategoriaFinanciera(datos) {
  return solicitar('/categorias/', {
    metodo: 'POST',
    json: datos
  });
}

export function actualizarCategoriaFinanciera(id, datos) {
  return solicitar(`/categorias/${id}`, {
    metodo: 'PATCH',
    json: datos
  });
}

export function desactivarCategoriaFinanciera(id) {
  return solicitar(
    `/categorias/${id}/desactivar`,
    { metodo: 'POST' }
  );
}


// PRESUPUESTOS

export function obtenerPresupuestos() {
  return solicitar('/presupuestos/');
}

export function crearPresupuesto(datos) {
  return solicitar('/presupuestos/', {
    metodo: 'POST',
    json: datos
  });
}

export function actualizarPresupuesto(id, datos) {
  return solicitar(`/presupuestos/${id}`, {
    metodo: 'PATCH',
    json: datos
  });
}


// METAS

export function obtenerMetas() {
  return solicitar('/metas/');
}

export function obtenerMeta(id) {
  return solicitar(`/metas/${id}`);
}

export function crearMeta(datos) {
  return solicitar('/metas/', {
    metodo: 'POST',
    json: datos
  });
}

export function actualizarMeta(id, datos) {
  return solicitar(`/metas/${id}`, {
    metodo: 'PATCH',
    json: datos
  });
}

export function desactivarMeta(id) {
  return solicitar(
    `/metas/${id}/desactivar`,
    { metodo: 'POST' }
  );
}

// Compatibilidad temporal con el backend del paso 25.
// La nueva interfaz ya no utiliza aportes sin cuenta.
export function aportarMeta(id, datos) {
  return solicitar(`/metas/${id}/aportes`, {
    metodo: 'POST',
    json: datos
  });
}


// RESERVAS VINCULADAS A CUENTAS — 25.1B

export function obtenerSaldosReservados() {
  return solicitar('/metas/reservas/cuentas');
}

export function obtenerDetalleReservasMeta(id) {
  return solicitar(`/metas/${id}/reservas`);
}

export function reservarDineroMeta(id, datos) {
  return solicitar(`/metas/${id}/reservas`, {
    metodo: 'POST',
    json: datos
  });
}

export function liberarDineroMeta(id, datos) {
  return solicitar(`/metas/${id}/liberaciones`, {
    metodo: 'POST',
    json: datos
  });
}
