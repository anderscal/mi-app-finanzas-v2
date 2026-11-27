"""Excepciones propias de la capa Business.

Independientes de HTTP, FastAPI y la interfaz de usuario.
"""

from enum import Enum


class CodigoError(str, Enum):

    AUTENTICACION_REQUERIDA = "AUTENTICACION_REQUERIDA"
    NO_AUTENTICADO = "NO_AUTENTICADO"
    PROHIBIDO = "PROHIBIDO"
    NO_ENCONTRADO = "NO_ENCONTRADO"
    CONFLICTO = "CONFLICTO"
    LIMITE_SOLICITUDES = "LIMITE_SOLICITUDES"
    VALIDACION = "VALIDACION"
    FUENTE_NO_DISPONIBLE = "FUENTE_NO_DISPONIBLE"
    EVIDENCIA_INCONSISTENTE = "EVIDENCIA_INCONSISTENTE"


class ErrorNegocio(Exception):

    def __init__(
        self,
        codigo: CodigoError,
        detalle: str,
    ):

        if not isinstance(codigo, CodigoError):

            raise TypeError(
                "Codigo de error de negocio invalido"
            )

        super().__init__(detalle)

        self.codigo = codigo
        self.detalle = detalle 