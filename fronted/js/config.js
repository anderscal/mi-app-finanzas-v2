// Configuración del frontend. Es el único archivo que hay que tocar
// al pasar de local a producción.

export const CONFIG = {
  // URL del backend FastAPI (sin "/" al final).
  // Local: uvicorn en el puerto 8000. Producción: la URL de Render.
  API_URL: 'http://127.0.0.1:8000',


  // TEMPORAL: el backend aún no tiene GET /categorias.
  // Son las categorías del script SQL (ids en el orden en que se insertaron).
  // Cuando exista el endpoint, se reemplaza por la respuesta real.
  CATEGORIAS_TEMPORALES: [
    { id_categoria: 1, nombre_categoria: 'Alimentación', tipo_categoria: 'GASTO' },
    { id_categoria: 2, nombre_categoria: 'Transporte', tipo_categoria: 'GASTO' },
    { id_categoria: 3, nombre_categoria: 'Restaurantes', tipo_categoria: 'GASTO' },
    { id_categoria: 4, nombre_categoria: 'Salario', tipo_categoria: 'INGRESO' },
  ],
};
