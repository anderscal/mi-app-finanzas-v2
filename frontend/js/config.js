// Configuracion del frontend para desarrollo y produccion.

const entornoLocal = [
  'localhost',
  '127.0.0.1',
  '[::1]'
].includes(window.location.hostname);

export const CONFIG = {
  API_URL: entornoLocal
    ? 'http://127.0.0.1:8000'
    : 'https://finanzas-personales-api-4rry.onrender.com',
};
