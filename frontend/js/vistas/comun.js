// Piezas que se repiten en varias pantallas.

import { icono, esc } from '../util.js';

export function banda(titulo, { atras = null, subtitulo = '', extra = '' } = {}) {
  return `
    <header class="banda">
      <div class="banda-fila">
        ${atras ? `<a class="btn-icono" href="${atras}" aria-label="Volver">${icono('atras')}</a>` : ''}
        <h1 class="banda-titulo">${esc(titulo)}</h1>
      </div>
      ${subtitulo ? `<p class="banda-sub">${esc(subtitulo)}</p>` : ''}
      ${extra}
    </header>`;
}

// Bloque para funciones que el backend todavía no ofrece.
export function pendienteBackend(texto, endpoint) {
  return `
    <div class="pendiente">
      <strong>Pendiente en el backend</strong>
      <span>${esc(texto)}</span>
      ${endpoint ? `<code>${esc(endpoint)}</code>` : ''}
    </div>`;
}

export function cargando(texto = 'Cargando…') {
  return `<p class="cargando">${esc(texto)}</p>`;
}

export function errorCarga(e) {
  if (e && e.estado === 0) return pendienteBackend('Este dato necesita un endpoint con token.', '');
  return `<p class="error-general">${esc(e?.message || 'No se pudo cargar.')}</p>`;
}
