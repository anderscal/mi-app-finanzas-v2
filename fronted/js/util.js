import { obtenerUsuario } from './sesion.js';
// Formatos para Colombia y utilidades de las vistas.

const pesos = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

// El backend envía los montos a veces como número y a veces como texto.
export function cop(valor) {
  return '$ ' + pesos.format(Math.round(Number(valor) || 0));
}

export function nombreMes(mes) {
  return MESES[mes - 1];
}

// "2026-11-05" → "5 nov" (sin pasar por Date para evitar el desfase de zona horaria)
export function fechaCorta(iso) {
  const [, m, d] = String(iso).split('-').map(Number);
  return `${d} ${MESES_CORTOS[m - 1]}`;
}

// Fecha de hoy en la zona horaria del dispositivo, formato AAAA-MM-DD.
export function hoyISO() {
  const h = new Date();
  const dos = (n) => String(n).padStart(2, '0');
  return `${h.getFullYear()}-${dos(h.getMonth() + 1)}-${dos(h.getDate())}`;
}

// Escapa texto que viene del usuario o del servidor antes de ponerlo en HTML.
export function esc(texto) {
  return String(texto ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function nuevoUUID() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

let temporizador;
export function aviso(texto, tipo = 'info') {
  const t = document.getElementById('toast');
  t.textContent = texto;
  t.dataset.tipo = tipo;
  t.classList.add('visible');
  clearTimeout(temporizador);
  temporizador = setTimeout(() => t.classList.remove('visible'), 4000);
}

// Guarda la última respuesta buena para mostrarla sin conexión.

function claveCacheUsuario(clave) {

  const idUsuario = Number(
    obtenerUsuario()?.id_usuario
  );

  if (
    !Number.isSafeInteger(idUsuario) ||
    idUsuario <= 0
  ) {
    return null;
  }

  return `fp:cache:usuario:${idUsuario}:${clave}`;
}


export function guardarCache(clave, datos) {

  const claveFinal = claveCacheUsuario(clave);

  if (!claveFinal) return;

  try {
    localStorage.setItem(
      claveFinal,
      JSON.stringify({
        datos,
        en: Date.now()
      })
    );
  } catch {
    // Almacenamiento no disponible.
  }
}


export function leerCache(clave) {

  const claveFinal = claveCacheUsuario(clave);

  if (!claveFinal) return null;

  try {
    const contenido = localStorage.getItem(
      claveFinal
    );

    return contenido
      ? JSON.parse(contenido)
      : null;

  } catch {
    return null;
  }
}


// Íconos de línea (sin imágenes externas).
const TRAZOS = {
  inicio: '<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  deudas: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
  mas: '<path d="M12 5v14M5 12h14"/>',
  metas: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/>',
  asistente: '<path d="M4 5h16v11H9l-5 4z"/>',
  transferir: '<path d="M4 8h14l-4-4M20 16H6l4 4"/>',
  atras: '<path d="M15 5l-7 7 7 7"/>',
  ojo: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  salir: '<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/>',
  lista: '<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>',
  nube: '<path d="M4 12a8 8 0 0 1 14-5l2-2v6h-6l2-2a5 5 0 1 0 1 6"/>',
  comida: '<path d="M7 3v8M5 3v5a2 2 0 0 0 4 0V3M7 11v10M17 3c-2 2-2 6 0 8v10"/>',
  maletin: '<rect x="3" y="7" width="18" height="12" rx="2"/><path d="M8 7V5h8v2"/>',
};

export function icono(nombre, tam = 22) {
  return `<svg aria-hidden="true" width="${tam}" height="${tam}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${TRAZOS[nombre] || ''}</svg>`;
}
