# Frontend — Finanzas Personales PWA

Interfaz desarrollada con HTML, CSS y JavaScript
modular, sin frameworks ni proceso de compilación.

## Ejecución local

Iniciar FastAPI desde backend.

Desde frontend:

```powershell
python -m http.server 5500
```

Abrir:

http://127.0.0.1:5500

La dirección de la API se configura en js/config.js.

Los orígenes autorizados se configuran mediante
CORS_ORIGINS en el backend.

## Componentes

| Archivo | Responsabilidad |
|---|---|
| js/app.js | Navegación y rutas |
| js/api.js | Comunicación con FastAPI |
| js/config.js | Configuración de la API |
| js/sesion.js | Gestión de sesión |
| js/offline-db.js | Persistencia en IndexedDB |
| js/offline.js | Operaciones sin conexión |
| js/sync.js | Sincronización de operaciones |
| js/rag-api.js | Comunicación con el asistente |
| js/vistas/ | Pantallas de la aplicación |
| js/vistas/password.js | Recuperación y cambio de contraseña |
| js/vistas/asistente.js | Consultas y evidencia financiera |
| css/estilos.css | Identidad visual |
| sw.js | Caché estática de la PWA |
| manifest.webmanifest | Instalación de la PWA |

## Diseño

Identidad visual verde esmeralda y dorado.

Interfaz adaptable a dispositivos móviles.

Mensajes breves y orientados al usuario.

La evidencia financiera y la información técnica
del asistente se presentan en secciones desplegables.

## Autenticación

- Registro.
- Inicio de sesión.
- Cambio de contraseña.
- Solicitud de recuperación.
- Restablecimiento mediante enlace temporal.

Las operaciones de autenticación requieren conexión.

Las contraseñas y los tokens de recuperación no
se almacenan en IndexedDB.

## Modo offline

Las operaciones financieras compatibles se guardan
localmente para su posterior sincronización.

No se permite iniciar una nueva sesión offline.

Los datos locales deben mantenerse aislados
por usuario.

No borrar IndexedDB si existen movimientos
pendientes de sincronizar.

## Asistente financiero

Utiliza la API RAG del backend.

El usuario debe autorizar el envío de su pregunta
y evidencia recuperada al proveedor externo.

Las consultas no modifican datos financieros.

El diagnóstico sin IA está disponible en la
sección Información técnica.

## Service Worker

Versión de referencia: fp-v31.

Actualizar la versión de caché cuando se modifiquen
los recursos estáticos.

No almacenar respuestas privadas de la API
en la caché del Service Worker.

## Producción

Actualizar js/config.js con la URL HTTPS del backend.

Configurar Content Security Policy en index.html.

Actualizar los orígenes CORS del backend.

Actualizar PWA_ORIGEN para los enlaces
de recuperación de contraseña.

Consultar el README principal para instalación,
arquitectura y pruebas.