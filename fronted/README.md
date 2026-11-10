# Frontend · Finanzas Personales (PWA)

HTML, CSS y JavaScript sin frameworks ni compilación. Se conecta a la API FastAPI de `../backend`.

## Cómo correrlo en local

1. Enciende el backend (desde `backend/`):

   ```bash
   python -m uvicorn app.main:app --reload
   ```

2. CORS ya está configurado en `backend/app/main.py` para `localhost:5500` y `5501`. Al desplegar, agrega ahí la URL del frontend en Render.

3. Sirve esta carpeta (desde `frontend/`):

   ```bash
   python -m http.server 5500
   ```

4. Abre <http://localhost:5500>. Regístrate o inicia sesión.

La URL del backend se cambia en `js/config.js` (`API_URL`).

## Estructura

| Archivo | Qué hace |
|---|---|
| `js/config.js` | URL del backend y categorías temporales |
| `js/api.js` | Una función por endpoint. Si cambia el backend, se ajusta aquí |
| `js/sesion.js` | Token JWT: guardar, leer, detectar vencimiento (30 min) |
| `js/offline.js` | Capa del modo sin conexión que usan las pantallas |
| `js/offline-db.js`, `js/sync.js` | Cola en IndexedDB y sincronización (copiados de `backend/JS/`) |
| `js/app.js` | Rutas (`#/inicio`, `#/registrar`…), barra inferior, eventos online/offline |
| `js/vistas/*.js` | Una pantalla por archivo |
| `sw.js` | Service Worker: la app abre sin internet |
| `css/estilos.css` | Identidad verde esmeralda + dorado de los mockups |

## Endpoints que usa

Todos piden token, salvo registro y login.

| Pantalla | Endpoint |
|---|---|
| Registro | `POST /auth/registro` (JSON) |
| Login | `POST /auth/login` (formulario, el correo va en `username`) |
| Perfil | `GET /auth/me` |
| Inicio: saldo y cuentas | `GET /auth/mis-cuentas` |
| Inicio: resumen del mes | `GET /consultas/resumen-mensual` |
| Inicio y Movimientos: historial | `GET /consultas/historial-mensual` |
| Deudas y Metas | `GET /consultas/planificacion` |
| Registrar movimiento | `POST /movimientos/normales` |
| Transferir entre cuentas (con GMF) | `POST /transferencias/` (con barra final) |
| Registrar pago o cobro de una obligación | `POST /obligaciones/abonos` |
| Anular un movimiento (Movimientos › tocar uno) | `POST /movimientos/{id}/anular` |

## Modo sin conexión

Usa los mismos módulos que el backend probó en `backend/JS/` (`js/offline-db.js` y `js/sync.js`); `js/offline.js` es la capa que llaman las pantallas.

- Funciona para **ingresos y gastos, transferencias y pagos o cobros de obligaciones**.
- Cada operación se guarda en IndexedDB (`finanzas_offline`) con su UUID y el usuario que la creó.
- Al volver la conexión (o al iniciar sesión) se envían **en orden**. El backend no las duplica porque reconoce el UUID, y la app solo borra la copia local si la respuesta trae ese mismo UUID.
- Si el backend rechaza una (por ejemplo, saldo insuficiente), **la cola se detiene ahí**: las siguientes pueden depender de ella. En **Movimientos › En este celular** se puede reintentar (salvo errores 422, que son datos inválidos) o descartar la copia local.
- Sin conexión, Inicio, Transferir y Pagar usan las últimas cuentas y obligaciones guardadas.

## Lo que el frontend espera del backend

| Necesita | Para | Mientras tanto |
|---|---|---|
| `GET /categorias` | Elegir categoría al registrar | Lista fija en `config.js` (ids 1–4 del script SQL) |
| GMF en `POST /movimientos/normales` | Casilla 4x1000 | Casilla deshabilitada |
| `POST /obligaciones` | Crear una deuda o un préstamo | Aviso en Deudas |
| Presupuestos y metas (crear, abonar) | Botones de Metas | Deshabilitados con "pronto" |
| Asistente (AI Gateway) | Pantalla Asistente | Pantalla informativa |
