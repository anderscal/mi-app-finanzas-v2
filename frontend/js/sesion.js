
const CLAVE_TOKEN = 'fp:token';
const CLAVE_USUARIO = 'fp:usuario';

function leer(clave) {
  try {
    return localStorage.getItem(clave);
  } catch {
    return null;
  }
}

function escribir(clave, valor) {
  try {
    if (valor === null) {
      localStorage.removeItem(clave);
    } else {
      localStorage.setItem(clave, valor);
    }
  } catch {
    // Almacenamiento no disponible.
  }
}

// Comprueba el vencimiento declarado en el JWT.
// La firma y los permisos se validan en FastAPI.
function vencimiento(token) {
  try {
    const parte = token
      .split('.')[1]
      .replace(/-/g, '+')
      .replace(/_/g, '/');

    const datos = JSON.parse(atob(parte));

    return typeof datos.exp === 'number'
      ? datos.exp * 1000
      : 0;

  } catch {
    return 0;
  }
}

export function guardarToken(token) {
  const anterior = leer(CLAVE_TOKEN);

  // Un token nuevo no debe asociarse
  // temporalmente con el usuario anterior.
  if (anterior !== token) {
    escribir(CLAVE_USUARIO, null);
  }

  escribir(CLAVE_TOKEN, token);
}

export function obtenerToken() {
  const token = leer(CLAVE_TOKEN);

  if (!token) return null;

  if (vencimiento(token) <= Date.now()) {
    cerrarSesion();
    return null;
  }

  return token;
}

export function minutosRestantes() {
  const token = leer(CLAVE_TOKEN);

  if (!token) return 0;

  return Math.max(
    0,
    Math.floor(
      (vencimiento(token) - Date.now()) / 60000
    )
  );
}

export function guardarUsuario(usuario) {
  const id = Number(usuario?.id_usuario);

  if (!Number.isSafeInteger(id) || id <= 0) {
    throw new Error(
      'No se pudo identificar al usuario.'
    );
  }

  escribir(
    CLAVE_USUARIO,
    JSON.stringify(usuario)
  );
}

export function obtenerUsuario() {
  try {
    return JSON.parse(leer(CLAVE_USUARIO)) || null;
  } catch {
    return null;
  }
}

export function cerrarSesion() {
  escribir(CLAVE_TOKEN, null);
  escribir(CLAVE_USUARIO, null);

  // No eliminamos IndexedDB:
  // podría contener operaciones financieras
  // pendientes del usuario que cerró sesión.
}

export function haySesion() {
  return (
    obtenerToken() !== null &&
    obtenerUsuario() !== null
  );
}
