// Guarda el token JWT y los datos básicos del usuario en el navegador.

const CLAVE_TOKEN = 'fp:token';
const CLAVE_USUARIO = 'fp:usuario';

function leer(clave) {
  try { return localStorage.getItem(clave); } catch { return null; }
}

function escribir(clave, valor) {
  try {
    if (valor === null) localStorage.removeItem(clave);
    else localStorage.setItem(clave, valor);
  } catch { /* almacenamiento bloqueado: la sesión dura solo en memoria */ }
}

// Lee el campo "exp" del JWT sin verificar la firma (eso lo hace el backend).
function vencimiento(token) {
  try {
    const parte = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const datos = JSON.parse(atob(parte));
    return typeof datos.exp === 'number' ? datos.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

export function guardarToken(token) {
  escribir(CLAVE_TOKEN, token);
}

// Devuelve el token solo si no ha vencido (el backend lo da por 30 minutos).
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
  return Math.max(0, Math.floor((vencimiento(token) - Date.now()) / 60000));
}

export function guardarUsuario(usuario) {
  escribir(CLAVE_USUARIO, JSON.stringify(usuario));
}

export function obtenerUsuario() {
  try { return JSON.parse(leer(CLAVE_USUARIO)) || null; } catch { return null; }
}

export function cerrarSesion() {
  escribir(CLAVE_TOKEN, null);
}

export function haySesion() {
  return obtenerToken() !== null;
}
