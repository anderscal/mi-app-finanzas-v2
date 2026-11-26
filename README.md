# Finanzas Personales — PWA

Aplicación web progresiva para la administración de
finanzas personales y gestión del conocimiento financiero.

Proyecto académico desarrollado mediante una arquitectura
de cinco capas, almacenamiento relacional, representación
semántica del conocimiento y recuperación dinámica
de información asistida por inteligencia artificial.

## 1. Funcionalidades

- Registro y autenticación de usuarios.
- Cambio y recuperación de contraseña.
- Administración de cuentas financieras.
- Registro de ingresos y gastos.
- Transferencias entre cuentas.
- Cálculo del Gravamen a los Movimientos Financieros (GMF).
- Administración de obligaciones y abonos.
- Presupuestos financieros.
- Metas de ahorro.
- Reservas y liberaciones de dinero.
- Anulación de movimientos.
- Historial y resumen financiero mensual.
- Operaciones compatibles sin conexión.
- Sincronización de operaciones pendientes.
- Asistente financiero mediante RAG dinámico.
- Diagnóstico de fuentes sin inteligencia artificial.

## 2. Tecnologías

### Frontend

- HTML5.
- CSS3.
- JavaScript modular.
- Progressive Web App.
- Service Worker.
- IndexedDB.

### Backend

- Python.
- FastAPI.
- SQLAlchemy.
- Pydantic.
- JWT.
- Argon2 mediante pwdlib.

### Persistencia y conocimiento

- PostgreSQL.
- Apache Jena Fuseki.
- TDB2.
- RDF y OWL.
- SPARQL.
- Docker.

### Servicios externos

- Google Gemini: planificación y generación asistida.
- Brevo: correo transaccional de recuperación.

## 3. Arquitectura

El sistema utiliza cinco capas:

1. Presentation:
   Interfaz PWA, routers HTTP y dependencias de autenticación.

2. Business:
   Reglas financieras, validaciones y coordinación
   de los procesos del sistema.

3. Services:
   Servicios técnicos de autenticación, correo
   electrónico e inteligencia artificial.

4. Persistence:
   Repositorios SQL, consultas SPARQL y acceso
   controlado a las fuentes de datos.

5. Database:
   PostgreSQL y Apache Jena Fuseki/TDB2.

Presentation accede a Business.
Business puede utilizar Services y Persistence.
Services puede utilizar Persistence cuando corresponda.
Persistence realiza el acceso a Database.

El punto de composición y los contratos compartidos
se encuentran sujetos a las excepciones expresamente
definidas en la auditoría arquitectónica.

## 4. Estructura del repositorio

    finanzas_personales/
    ├── backend/
    │   ├── app/
    │   │   ├── business/
    │   │   ├── database/
    │   │   ├── models/
    │   │   ├── persistence/
    │   │   ├── routers/
    │   │   ├── schemas/
    │   │   ├── services/
    │   │   ├── tests/
    │   │   └── main.py
    │   ├── migraciones/
    │   ├── semantica/
    │   │   ├── consultas/
    │   │   ├── docker/
    │   │   ├── migraciones/
    │   │   └── ontologia/
    │   ├── .env.example
    │   ├── .env.test.example
    │   └── requirements.txt
    ├── frontend/
    │   ├── css/
    │   ├── icons/
    │   ├── js/
    │   ├── index.html
    │   ├── manifest.webmanifest
    │   └── sw.js
    ├── .gitignore
    └── README.md

## 5. Instalación local

Requisitos:

- Python 3.14.3, versión utilizada en las pruebas locales.
- PostgreSQL.
- Docker Desktop.
- Navegador compatible con Service Workers e IndexedDB.

Desde backend:

```powershell
python -m venv .venv

& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Crear .env a partir de .env.example.

Configurar las credenciales PostgreSQL y generar una
clave JWT aleatoria de al menos 64 caracteres.

```powershell
& .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

No publicar la clave generada.

## 6. Inicialización de PostgreSQL

Crear una base de datos vacía.

Restaurar migraciones/esquema_base.sql mediante
psql con detención ante errores.

Ejecutar migraciones/categorias_sistema.sql.

El esquema base representa la estructura consolidada.
No volver a aplicar migraciones históricas ya incluidas.

No ejecutar los archivos de inicialización sobre una
base existente con información financiera.

Configurar una segunda base independiente para pruebas
y asignar sus credenciales en .env.test.

## 7. Inicialización de Fuseki

Desde backend, con Docker disponible:

```powershell
docker compose -f semantica/docker/compose.yaml up -d
```

Cargar la ontología inicial:

```powershell
& .\.venv\Scripts\python.exe semantica/cargar_ttl_263.py
```

Dataset local:

http://127.0.0.1:3030/finanzas_demo

Los datos TDB2 se conservan en un volumen Docker
persistente.

No utilizar docker compose down -v.

Para habilitar la sincronización semántica:

    SEMANTICA_AUTO_SYNC=1

La API de Fuseki no debe exponerse públicamente
sin autenticación y protección de transporte.

## 8. Ejecutar la aplicación

Backend, desde su directorio:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend, desde su directorio:

```powershell
python -m http.server 5500
```

PWA:

http://127.0.0.1:5500

Documentación API:

http://127.0.0.1:8000/docs

## 9. Asistente financiero RAG

El asistente utiliza planificación dinámica mediante
Google Gemini.

Las consultas se validan mediante un catálogo
y un contrato estructurado.

La recuperación se realiza mediante repositorios
controlados y limitados al usuario autenticado.

El asistente puede recuperar evidencia relacional
desde PostgreSQL y evidencia semántica desde Fuseki.

Si un plan no supera la validación, se permite un
intento controlado de corrección.

El asistente no ejecuta operaciones financieras
de escritura ni consultas SQL/SPARQL arbitrarias
generadas por la inteligencia artificial.

Las respuestas presentan referencias a las fuentes
y permiten consultar la evidencia recuperada.

El envío a Gemini requiere consentimiento explícito.

Para activar el servicio, configurar:

    RAG_IA_HABILITADA=1
    GEMINI_API_KEY
    GEMINI_RAG_MODEL

El diagnóstico sin IA no requiere utilizar Gemini.

Las respuestas pueden contener errores y no
constituyen asesoramiento financiero profesional.

## 10. Recuperación de contraseña

El cambio de contraseña requiere autenticación
y verificación de la contraseña actual.

La recuperación utiliza Brevo mediante HTTPS.

Los tokens son aleatorios, tienen una vigencia
de 15 minutos y se almacenan mediante su hash.

Los enlaces son de un solo uso.

El cambio de contraseña invalida los JWT anteriores.

Para habilitar los correos:

    RECUPERACION_HABILITADA=1
    BREVO_API_KEY
    BREVO_REMITENTE
    PWA_ORIGEN

La recuperación requiere conexión a internet.

## 11. Funcionamiento sin conexión

La PWA permite utilizar datos locales disponibles
cuando existe una sesión previamente iniciada.

Las operaciones financieras compatibles se almacenan
en IndexedDB y se sincronizan posteriormente.

Los UUID de operación permiten controlar duplicados.

No se permite iniciar una sesión nueva, recuperar
contraseñas ni consultar Gemini sin conexión.

No eliminar IndexedDB cuando existan operaciones
pendientes de sincronizar.

## 12. Pruebas

Auditoría arquitectónica:

```powershell
& .\.venv\Scripts\python.exe auditoria_arquitectura_282d.py
```

Regresión general:

```powershell
& .\.venv\Scripts\python.exe -m pytest app/tests -v -x --tb=short --ignore=app/tests/test_fuseki_tdb2_263.py --disable-warnings
```

Persistencia TDB2, con FastAPI detenido:

```powershell
& .\.venv\Scripts\python.exe -m pytest app/tests/test_fuseki_tdb2_263.py -v -x --tb=short --disable-warnings
```

Utilizar una base independiente de pruebas y un
entorno Fuseki local de desarrollo.

No ejecutar las pruebas contra servicios productivos.

Resultado de referencia reportado al finalizar
el Paso 28.4 D:

- 243 pruebas de regresión aprobadas.
- 71 pruebas RAG incluidas en la regresión.
- Cero hallazgos arquitectónicos.

## 13. Seguridad

- No publicar archivos .env ni .env.test.
- No compartir claves JWT, Gemini, Brevo o PostgreSQL.
- No publicar respaldos con información de usuarios.
- Mantener el aislamiento entre usuarios.
- Utilizar HTTPS en producción.
- Limitar los orígenes permitidos por CORS.
- Proteger el acceso externo a Fuseki.
- Evitar ejecutar pruebas sobre datos reales.

## 14. Despliegue

Infraestructura prevista:

- PostgreSQL: Neon.
- Apache Jena Fuseki: Railway.
- Backend FastAPI: Render.
- Frontend PWA: Render.

El despliegue permanece pendiente de la validación
final de seguridad, configuración y compatibilidad
con el entorno productivo.

## 15. Estado

Versión local con funcionalidades financieras,
gestión del conocimiento, RAG dinámico y
recuperación de contraseña implementadas.

Las configuraciones productivas se documentarán
durante la etapa de despliegue.