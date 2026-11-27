// Modo claro / oscuro. Recuerda la elección en este dispositivo;
// la primera vez sigue la preferencia del sistema operativo.

const CLAVE = 'fp-tema';
const COLOR_BARRA = { claro: '#0B7A57', oscuro: '#0C5A42' };

export function temaActual() {
  return document.documentElement.dataset.tema === 'oscuro' ? 'oscuro' : 'claro';
}

function aplicar(tema, animar) {
  const raiz = document.documentElement;
  if (animar) {
    raiz.classList.add('tema-cambiando');
    setTimeout(() => raiz.classList.remove('tema-cambiando'), 400);
  }
  if (tema === 'oscuro') raiz.dataset.tema = 'oscuro';
  else delete raiz.dataset.tema;
  document.querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', COLOR_BARRA[tema]);
  document.querySelectorAll('.btn-tema').forEach(pintarBoton);
}

function pintarBoton(b) {
  const oscuro = temaActual() === 'oscuro';
  b.setAttribute('aria-pressed', String(oscuro));
  b.setAttribute('aria-label', oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
  b.title = oscuro ? 'Modo claro' : 'Modo oscuro';
}

export function alternarTema() {
  const nuevo = temaActual() === 'oscuro' ? 'claro' : 'oscuro';
  try { localStorage.setItem(CLAVE, nuevo); } catch { /* sin almacenamiento: solo esta sesión */ }
  aplicar(nuevo, true);
}

function crearBoton(flotante) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'btn-tema' + (flotante ? ' flotante' : '');
  b.innerHTML = `
    <svg class="ico-sol" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4.2"/>
      <path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/>
    </svg>
    <svg class="ico-luna" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M20.2 14.6A8.4 8.4 0 0 1 9.4 3.8a.6.6 0 0 0-.8-.7A9.2 9.2 0 1 0 20.9 15.4a.6.6 0 0 0-.7-.8Z"/>
    </svg>`;
  b.addEventListener('click', alternarTema);
  pintarBoton(b);
  return b;
}

// Coloca el botón en la parte superior de la vista actual.
function ubicarBoton(app) {
  if (app.querySelector('.btn-tema')) return;
  const banda = app.querySelector('.banda');
  if (banda) {
    const acciones = banda.querySelector('.banda-acciones');
    if (acciones) { acciones.prepend(crearBoton(false)); return; }
    banda.classList.add('con-tema');
    banda.append(crearBoton(false));
    return;
  }
  app.append(crearBoton(true));
}

export function iniciarTema() {
  // Sigue al sistema mientras el usuario no haya elegido.
  const media = matchMedia('(prefers-color-scheme: dark)');
  media.addEventListener?.('change', e => {
    let guardado = null;
    try { guardado = localStorage.getItem(CLAVE); } catch { /* */ }
    if (!guardado) aplicar(e.matches ? 'oscuro' : 'claro', true);
  });
  aplicar(temaActual(), false);

  const app = document.getElementById('app');
  const observador = new MutationObserver(() => ubicarBoton(app));
  observador.observe(app, { childList: true, subtree: true });
  ubicarBoton(app);
}
