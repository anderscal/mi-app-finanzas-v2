// Una función por endpoint del backend FastAPI.
// Si el backend cambia una ruta o un campo, se ajusta aquí y en ningún otro lugar.

import { CONFIG } from './config.js';
import { obtenerToken, cerrarSesion } from './sesion.js';

export class ErrorApi extends Error {
  constructor(estado, mensaje) {
    super(mensaje);
    this.estado = estado;
  }
}

// Fallo de red: sin internet, backend apagado o bloqueado por CORS.
export class ErrorDeRed extends Error { }

// Convierte el "detail" de FastAPI en un texto legible.
// 422 trae una lista de errores de Pydantic; los demás, un texto.
function mensajeDeError(cuerpo, estado) {
  const detalle = cuerpo && cuerpo.detail;
  if (typeof detalle === 'string') return detalle;
  if (Array.isArray(detalle) && detalle.length) {
    return detalle
      .map((e) => {
        const campo = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : '';
        const texto = String(e.msg || '').replace(/^Value error, /, '');
        return campo && campo !== 'body' ? `${campo}: ${texto}` : texto;
      })
      .join(' · ');
  }
  return `El servidor respondió con error ${estado}`;
}

async function solicitar(ruta, { metodo = 'GET', json, formulario, conToken = true } = {}) {
  const encabezados = {};
  let cuerpo;

  if (json !== undefined) {
    encabezados['Content-Type'] = 'application/json';
    cuerpo = JSON.stringify(json);
  } else if (formulario !== undefined) {
    encabezados['Content-Type'] = 'application/x-www-form-urlencoded';
    cuerpo = new URLSearchParams(formulario).toString();
  }

  if (conToken) {
    const token = obtenerToken();
    if (!token) {
      location.hash = '#/login';
      throw new ErrorApi(401, 'Tu sesión venció. Vuelve a iniciar sesión.');
    }
    encabezados.Authorization = `Bearer ${token}`;
  }

  let respuesta;
  try {
    respuesta = await fetch(CONFIG.API_URL + ruta, { method: metodo, headers: encabezados, body: cuerpo });
  } catch {
    throw new ErrorDeRed('No hay conexión con el servidor.');
  }

  let datos = null;
  try { datos = await respuesta.json(); } catch { /* respuesta sin cuerpo */ }

  if (!respuesta.ok) {
    if (respuesta.status === 401 && conToken) {
      cerrarSesion();
      location.hash = '#/login';
    }
    throw new ErrorApi(respuesta.status, mensajeDeError(datos, respuesta.status));
  }
  return datos;
}

// ---------- Autenticación ----------

// POST /auth/registro  (JSON)  → 201 { id_usuario, nombre_1, ..., email }
export function registrarUsuario({ nombre_1, nombre_2, apellido_1, apellido_2, email, password }) {
  return solicitar('/auth/registro', {
    metodo: 'POST',
    conToken: false,
    json: {
      nombre_1,
      nombre_2: nombre_2 || null,
      apellido_1,
      apellido_2: apellido_2 || null,
      email,
      password,
    },
  });
}

// POST /auth/login  (formulario, no JSON) → { access_token, token_type }
// FastAPI usa OAuth2PasswordRequestForm: el correo va en "username".
export function iniciarSesion(email, password) {
  return solicitar('/auth/login', {
    metodo: 'POST',
    conToken: false,
    formulario: { username: email, password },
  });
}

// GET /auth/me → datos del usuario autenticado
export function obtenerPerfil() {
  return solicitar('/auth/me');
}

// ---------- Cuentas ----------

// GET /auth/mis-cuentas → { saldo_general, total_cuentas, cuentas[] }
export function obtenerMisCuentas() {
  return solicitar('/auth/mis-cuentas');
}

/**
 * POST /cuentas/
 * Crea una cuenta financiera del usuario autenticado.
 *
 * El backend obtiene id_usuario desde JWT.
 * No se permite especificarlo desde el frontend.
 */
export function crearCuentaFinanciera(datos) {
  return solicitar('/cuentas/', {
    metodo: 'POST',
    json: datos
  });
}


export function actualizarCuentaFinanciera(idCuenta, datos) {
  return solicitar(`/cuentas/${idCuenta}`, {
    metodo: 'PATCH',
    json: datos
  });
}

export function desactivarCuentaFinanciera(idCuenta) {
  return solicitar(`/cuentas/${idCuenta}/desactivar`, {
    metodo: 'POST'
  });
}

// ---------- Movimientos ----------

// POST /movimientos/normales → { id_movimiento, uuid_local, tipo, monto, creado, mensaje }
// Es idempotente: reenviar el mismo uuid_local no duplica el movimiento.
export function crearMovimientoNormal(movimiento) {
  return solicitar('/movimientos/normales', { metodo: 'POST', json: movimiento });
}

// ---------- Transferencias ----------

// POST /transferencias
// → { id_transferencia, uuid_operacion, id_movimiento_salida, id_movimiento_entrada,
//     monto, monto_gmf, creado, mensaje }
// El backend crea la transferencia y sus dos movimientos en una sola transacción.
// Es idempotente: reenviar el mismo uuid_operacion no la duplica.

export function crearTransferencia({ uuid_operacion, id_cuenta_origen, id_cuenta_destino, monto, fecha_transferencia, motivo, aplica_gmf }) {
  const cuerpo = { uuid_operacion, id_cuenta_origen, id_cuenta_destino, monto, fecha_transferencia, aplica_gmf };
  if (motivo) cuerpo.motivo = motivo; // si no se envía, el backend usa "Movimiento interno"
  // La ruta del backend es "/transferencias/" (con barra final). Sin ella, FastAPI
  // responde con una redirección que en producción puede romper la petición.
  return solicitar('/transferencias/', { metodo: 'POST', json: cuerpo });
}

// POST /movimientos/{id}/anular → { id_movimiento, estado: "ANULADO", mensaje }
// Normal: anula solo ese movimiento. Transferencia: anula la salida y la entrada.
// Obligación: anula el abono y el backend recalcula si la obligación sigue saldada.
export function anularMovimiento(idMovimiento) {
  return solicitar(`/movimientos/${idMovimiento}/anular`, { metodo: 'POST' });
}

// ---------- Obligaciones ----------

// POST /obligaciones/abonos
// → { id_movimiento, id_obligacion, uuid_local, tipo, monto, monto_pendiente, creado, mensaje }
// POR_PAGAR crea un GASTO (pago); POR_COBRAR crea un INGRESO (cobro).
// Si el pendiente llega a 0, el backend pasa la obligación a SALDADA.
export function registrarAbono({ uuid_local, id_cuenta, id_obligacion, monto, fecha_movimiento, descripcion }) {
  return solicitar('/obligaciones/abonos', {
    metodo: 'POST',
    json: { uuid_local, id_cuenta, id_obligacion, monto, fecha_movimiento, descripcion: descripcion || null },
  });
}

// ---------- Consultas (del usuario que inició sesión) ----------

// GET /consultas/resumen-mensual?anio&mes
// → { ingresos_ordinarios, gastos_ordinarios, balance_ordinario, gmf_total, ... }
export function obtenerResumenMensual(anio, mes) {
  return solicitar(`/consultas/resumen-mensual?anio=${anio}&mes=${mes}`);
}

// GET /consultas/historial-mensual?anio&mes → { total_movimientos, movimientos[] }
export function obtenerHistorialMensual(anio, mes) {
  return solicitar(`/consultas/historial-mensual?anio=${anio}&mes=${mes}`);
}

// GET /consultas/planificacion → { presupuestos[], metas[], obligaciones[] }
export function obtenerPlanificacion() {
  return solicitar('/consultas/planificacion');
}


/**
 * GET /categorias/
 *
 * Devuelve las categorías activas:
 * - Categorías del sistema.
 * - Categorías personales del usuario autenticado.
 */
export function obtenerCategorias() {
  return solicitar('/categorias/');
}


/**
 * POST /categorias/
 * Crea una categoría personal.
 */
export function crearCategoriaFinanciera(datos) {
  return solicitar('/categorias/', {
    metodo: 'POST',
    json: datos
  });
}


/**
 * PATCH /categorias/{id_categoria}
 * Actualiza el nombre de una categoría personal.
 */
export function actualizarCategoriaFinanciera(
  idCategoria,
  datos
) {
  return solicitar(`/categorias/${idCategoria}`, {
    metodo: 'PATCH',
    json: datos
  });
}


/**
 * POST /categorias/{id_categoria}/desactivar
 * Desactiva lógicamente una categoría personal.
 */
export function desactivarCategoriaFinanciera(idCategoria) {
  return solicitar(
    `/categorias/${idCategoria}/desactivar`,
    {
      metodo: 'POST'
    }
  );
}

