"""Traduccion de errores de Business a HTTP.

Capa Presentation.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.business.errores import (
    CodigoError,
    ErrorNegocio,
)


ESTADOS_HTTP = {
    CodigoError.AUTENTICACION_REQUERIDA: 401,
    CodigoError.NO_AUTENTICADO: 401,
    CodigoError.PROHIBIDO: 403,
    CodigoError.NO_ENCONTRADO: 404,
    CodigoError.CONFLICTO: 409,
    CodigoError.VALIDACION: 422,
    CodigoError.LIMITE_SOLICITUDES: 429,
    CodigoError.FUENTE_NO_DISPONIBLE: 503,
    CodigoError.EVIDENCIA_INCONSISTENTE: 502,
}


async def manejar_error_negocio(
    request: Request,
    error: ErrorNegocio,
):

    encabezados = None

    if (
        error.codigo
        == CodigoError.AUTENTICACION_REQUERIDA
    ):

        encabezados = {
            "WWW-Authenticate": "Bearer",
        }

    return JSONResponse(
        status_code=ESTADOS_HTTP[error.codigo],

        content={
            "detail": error.detalle,
        },

        headers=encabezados,
    )