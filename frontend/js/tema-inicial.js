// Aplica el tema guardado antes de pintar la página, para que no parpadee en blanco.
// Es un archivo aparte (no un <script> en línea) porque la CSP solo permite scripts propios.
(function () {
  var t = null;
  try { t = localStorage.getItem('fp-tema'); } catch (e) { /* sin almacenamiento */ }
  if (t === 'oscuro' || (!t && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.dataset.tema = 'oscuro';
  }
})();
