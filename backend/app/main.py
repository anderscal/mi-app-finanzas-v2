from fastapi import FastAPI

from app.routers import (
    auth_router,
    consulta_router,
    movimiento_router,
    obligacion_router,
    transferencia_router,
)


app = FastAPI(
    title="API Finanzas Personales",
    description=(
        "Backend del sistema de "
        "gestión financiera personal"
    ),
    version="1.0.0"
)


app.include_router(
    auth_router.router
)

app.include_router(
    movimiento_router.router
)

app.include_router(
    transferencia_router.router
)

app.include_router(
    obligacion_router.router
)

app.include_router(
    consulta_router.router
)


@app.get("/")
def inicio():
    return {
        "mensaje":
            "Bienvenido a la API de Finanzas Personales",
        "estado": "funcionando"
    }


@app.get("/salud")
def verificar_salud():
    return {
        "servicio": "FastAPI",
        "estado": "activo"
    }