"""Casos de uso de consulta y publicacion RDF."""

import os

from decimal import (
    Decimal,
    InvalidOperation,
)

from sqlalchemy.exc import SQLAlchemyError

from app.business.errores import (
    CodigoError,
    ErrorNegocio,
)

from app.business.semantica_auto_sync import (
    publicar_revision,
)

from app.persistence.fuseki_client import (
    FusekiNoDisponible,
)

from app.persistence.semantica_consulta_repository import (
    obtener_filas_cuentas,
)


def sincronizar_semantica(
    db,
    id_usuario,
):

    if os.getenv(
        "SEMANTICA_EXPORTACION_LOCAL",
        "0",
    ) != "1":

        raise ErrorNegocio(
            CodigoError.PROHIBIDO,

            "La exportación RDF local no está habilitada",
        )

    try:

        resultado = publicar_revision(
            db,
            id_usuario,
            forzar=True,
        )

    except (
        FusekiNoDisponible,
        SQLAlchemyError,
    ) as exc:

        raise ErrorNegocio(
            CodigoError.FUENTE_NO_DISPONIBLE,

            "No fue posible publicar "
            "la instantánea RDF",
        ) from exc

    if resultado is None:

        raise ErrorNegocio(
            CodigoError.FUENTE_NO_DISPONIBLE,

            "La revisión RDF cambió "
            "durante su publicación",
        )

    return {
        "resultado": "sincronizado",

        "id_usuario": id_usuario,

        **resultado,

        "nota": (
            "Instantánea RDF; "
            "PostgreSQL es la fuente de verdad"
        ),
    }


def consultar_cuentas_semanticas(
    id_usuario,
):

    try:

        filas = obtener_filas_cuentas(
            id_usuario
        )

    except FusekiNoDisponible as exc:

        raise ErrorNegocio(
            CodigoError.FUENTE_NO_DISPONIBLE,

            str(exc),
        ) from exc

    cuentas = []

    for fila in filas:

        try:

            datos = {
                k: fila[k]["value"]

                for k in (
                    "id",
                    "nombre",
                    "real",
                    "reservado",
                    "libre",
                )
            }

            real, reservado, libre = (
                Decimal(datos[k])

                for k in (
                    "real",
                    "reservado",
                    "libre",
                )
            )

            if not all(
                x.is_finite()

                for x in (
                    real,
                    reservado,
                    libre,
                )
            ):

                raise ValueError(
                    "Importe RDF no finito"
                )

            if real - reservado != libre:

                raise ValueError(
                    "Saldo RDF inconsistente"
                )

            cuentas.append({

                "id_cuenta": int(
                    datos["id"]
                ),

                "nombre_cuenta": datos[
                    "nombre"
                ],

                "saldo_real": str(real),

                "monto_reservado": str(
                    reservado
                ),

                "saldo_libre": str(libre),
            })

        except (
            KeyError,
            ValueError,
            InvalidOperation,
            TypeError,
        ) as exc:

            raise ErrorNegocio(
                CodigoError.EVIDENCIA_INCONSISTENTE,

                "Respuesta semántica inconsistente",
            ) from exc

    return {

        "id_usuario": id_usuario,

        "fuente": (
            "Fuseki/TDB2 (última sincronización)"
        ),

        "actualizacion_automatica": False,

        "cuentas": cuentas,
    }