import { icono, esc } from '../util.js';


export function banda(
  titulo,
  {
    atras = null,
    subtitulo = '',
    extra = ''
  } = {}
) {

  return `

    <header class="banda">

      <div class="banda-fila">

        ${
          atras
            ? `
              <a
                class="btn-icono"
                href="${esc(atras)}"
                aria-label="Volver"
              >
                ${icono('atras')}
              </a>`
            : ''
        }

        <h1 class="banda-titulo">
          ${esc(titulo)}
        </h1>

      </div>

      ${
        subtitulo
          ? `
            <p class="banda-sub">
              ${esc(subtitulo)}
            </p>`
          : ''
      }

      ${extra}

    </header>`;
}


export function pendienteBackend() {

  return `
    <p class="error-general">
      Función no disponible por ahora.
    </p>`;
}


export function cargando(texto = 'Cargando…') {

  return `
    <p class="cargando">
      ${esc(texto)}
    </p>`;
}


export function errorCarga(e) {

  let texto =
    'No se pudieron cargar los datos.';


  if (e?.estado === 0) {

    return pendienteBackend();
  }


  if (e?.estado === 401) {

    texto =
      'Tu sesión venció. Inicia sesión.';

  } else if (e?.estado === 403) {

    texto =
      'No tienes acceso a estos datos.';

  } else if (e?.estado === 404) {

    texto =
      'No se encontraron los datos.';

  } else if (e?.estado === 429) {

    texto =
      'Intenta nuevamente más tarde.';

  } else if (e?.estado >= 500) {

    texto =
      'Servicio temporalmente no disponible.';

  } else if (
    e?.constructor?.name === 'ErrorDeRed'
  ) {

    texto =
      'Sin conexión con el servicio.';
  }


  return `
    <p class="error-general">
      ${esc(texto)}
    </p>`;
}