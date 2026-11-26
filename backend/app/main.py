"""Punto de entrada y composicion de la aplicacion."""

import os

from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import event

from app.persistence.database import SesionFinanciera

from app.business import semantica_auto_sync as sync

from app.business.errores import ErrorNegocio

from app.routers.errores import manejar_error_negocio

from app.routers import (
    auth_router,
    consulta_router,
    cuenta_router,
    movimiento_router,
    obligacion_router,
    transferencia_router,
    categoria_router,
    presupuesto_router,
    meta_router,
)


# ========================================
# CONFIGURACION DE ORIGENES CORS
# ========================================

ORIGENES_LOCALES = (
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:5501",
    "http://localhost:5501",
)


def obtener_origenes_cors():

    configuracion = os.getenv(
        "CORS_ORIGINS"
    )

    if configuracion is None:
        return list(ORIGENES_LOCALES)

    origenes = []

    for valor in configuracion.split(","):

        origen = valor.strip()

        if not origen:
            continue

        try:

            url = urlsplit(origen)

            # Fuerza la validacion del puerto.
            puerto = url.port

        except ValueError as error:

            raise RuntimeError(
                "Origen CORS invalido"
            ) from error

        if (
            "*" in origen

            or url.scheme not in {"http", "https"}

            or not url.hostname

            or url.username is not None

            or url.password is not None

            or url.path

            or url.query

            or url.fragment

            or (
                puerto is not None
                and puerto <= 0
            )
        ):

            raise RuntimeError(
                "CORS_ORIGINS contiene un origen invalido"
            )

        if (
            url.scheme == "http"

            and url.hostname not in {
                "localhost",
                "127.0.0.1",
                "::1",
            }
        ):

            raise RuntimeError(
                "Los origenes externos deben utilizar HTTPS"
            )

        if origen not in origenes:

            origenes.append(origen)

    if not origenes:

        raise RuntimeError(
            "CORS_ORIGINS no contiene origenes autorizados"
        )

    return origenes


# ========================================
# EVENTOS DE SINCRONIZACION SEMANTICA
# ========================================

for nombre_evento, funcion_evento in (
    ("before_flush", sync._marcar_cambios),
    ("after_commit", sync._publicar_despues_de_commit),
    ("after_rollback", sync._limpiar_rollback),
):

    if not event.contains(
        SesionFinanciera,
        nombre_evento,
        funcion_evento,
    ):

        event.listen(
            SesionFinanciera,
            nombre_evento,
            funcion_evento,
        )


# ========================================
# APLICACION FASTAPI
# ========================================

app = FastAPI(
    title="API Finanzas Personales",

    description=(
        "Backend del sistema de "
        "gestión financiera personal"
    ),

    version="1.0.0",
)


app.add_exception_handler(
    ErrorNegocio,
    manejar_error_negocio,
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=obtener_origenes_cors(),

    allow_credentials=False,

    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "OPTIONS",
    ],

    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
)


# ========================================
# REGISTRO DE ROUTERS
# ========================================

app.include_router(auth_router.router)
app.include_router(cuenta_router.router)
app.include_router(movimiento_router.router)
app.include_router(transferencia_router.router)
app.include_router(obligacion_router.router)
app.include_router(consulta_router.router)
app.include_router(categoria_router.router)
app.include_router(presupuesto_router.router)
app.include_router(meta_router.router)


@app.get("/")
def inicio():

    return {
        "mensaje": (
            "Bienvenido a la API de Finanzas Personales"
        ),

        "estado": "funcionando",
    }


@app.get("/salud")
def verificar_salud():

    return {
        "servicio": "FastAPI",

        "estado": "activo",
    }