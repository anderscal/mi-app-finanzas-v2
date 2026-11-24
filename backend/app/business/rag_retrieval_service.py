"""Recuperacion hibrida del RAG. Business."""

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.business.rag_contrato import (
    CATALOGO,
    Consulta,
    preparar_consulta,
)

from app.business.rag_contexto_ia import (
    serializar,
)

from app.persistence.rag_consulta_repository import (
    ejecutar_consulta_sql,
)

from app.persistence.rag_semantico_consulta_repository import (
    ejecutar_consulta_rdf,
)

from app.persistence.rag_semantico_basico_repository import (
    obtener_contexto_semantico_basico,
)

from app.persistence.rag_semantico_repository import (
    EvidenciaSemanticaInvalida,
)

from app.services.fuseki_client import (
    consultar_select,
    FusekiNoDisponible,
)

from app.services.semantica_auto_sync import (
    asegurar_actualizacion_para_rag,
)


class ErrorRAG(Exception):

    def __init__(self, codigo, mensaje):

        super().__init__(mensaje)

        self.codigo = codigo


def evaluar_vigencia_rdf(
    fecha_texto,
    ahora=None,
):

    desconocida = {
        "estado": "DESCONOCIDA",
        "antiguedad_horas": None,
    }

    if not isinstance(fecha_texto, str):
        return desconocida

    try:

        fecha = datetime.fromisoformat(
            fecha_texto.replace(
                "Z", "+00:00"
            )
        )

    except (
        ValueError,
        TypeError,
        OverflowError,
    ):

        return desconocida

    if fecha.tzinfo is None:
        return desconocida

    ahora = (
        ahora
        or datetime.now(timezone.utc)
    )

    if ahora.tzinfo is None:
        return desconocida

    horas = (
        ahora.astimezone(timezone.utc)
        - fecha.astimezone(timezone.utc)
    ).total_seconds() / 3600

    if horas < -(5 / 60):
        return desconocida

    horas = max(horas, 0)

    return {
        "estado": (
            "RECIENTE"
            if horas <= 24
            else "ANTIGUA"
        ),

        "antiguedad_horas": round(
            horas, 2
        ),
    }


def _preparar_semantica(db, usuario):

    asegurar_actualizacion_para_rag(
        db,
        usuario,
    )

    contexto = obtener_contexto_semantico_basico(
        id_usuario=usuario,

        incluir_categorias=False,

        ejecutar=consultar_select,
    )

    vigencia = evaluar_vigencia_rdf(
        contexto.get("fecha_instantanea")
    )

    if vigencia["estado"] != "RECIENTE":

        raise ErrorRAG(
            409,

            "No se puede verificar que el conocimiento "
            "semántico esté actualizado. "
            "La consulta requiere una instantánea RDF vigente.",
        )

    return {
        "fecha_instantanea": contexto[
            "fecha_instantanea"
        ],

        "vigencia": vigencia["estado"],

        "antiguedad_horas": vigencia[
            "antiguedad_horas"
        ],
    }


def recuperar_plan(
    db,
    usuario,
    plan,
    registro,
):

    if type(usuario) is not int or usuario <= 0:

        raise ErrorRAG(
            403,
            "Usuario no autorizado.",
        )

    # Se validan y convierten todas las consultas
    # antes de ejecutar cualquiera de ellas.

    try:

        consultas = [
            preparar_consulta(
                consulta,
                registro.restaurar_filtro,
            )

            for consulta in plan.consultas
        ]

    except ValueError as error:

        raise ErrorRAG(
            422,
            "El plan contiene filtros no válidos.",
        ) from error

    resultados = []

    semantica = None

    try:

        if any(
            consulta["entidad"].startswith("rdf_")

            for consulta in consultas
        ):

            semantica = _preparar_semantica(
                db,
                usuario,
            )

        for indice, consulta in enumerate(
            consultas,
            start=1,
        ):

            if consulta["entidad"].startswith("rdf_"):

                resultado = ejecutar_consulta_rdf(
                    usuario,
                    consulta,
                    consultar_select,
                )

                resultado.update({
                    "fecha_instantanea": semantica[
                        "fecha_instantanea"
                    ],
                    "vigencia_rdf": semantica[
                        "vigencia"
                    ],
                })

            else:

                resultado = ejecutar_consulta_sql(
                    db,
                    usuario,
                    consulta,
                )

            resultado.update({

                "referencia": f"E{indice}",

                "campos": consulta["campos"],

                "campo_agregado": consulta["campo"],

                "filtros": consulta["filtros"],

                "agrupar_por": consulta["agrupar_por"],

                "orden_campo": consulta["orden_campo"],

                "descendente": consulta["descendente"],
            })

            resultados.append(resultado)

    except FusekiNoDisponible as error:

        raise ErrorRAG(
            503,

            "Fuseki no está disponible. "
            "No se pudo recuperar el conocimiento "
            "semántico solicitado.",
        ) from error

    except EvidenciaSemanticaInvalida as error:

        raise ErrorRAG(
            409,

            "No se obtuvo evidencia semántica válida.",
        ) from error

    except SQLAlchemyError as error:

        raise ErrorRAG(
            503,

            "No fue posible recuperar los datos financieros.",
        ) from error

    except RuntimeError as error:

        raise ErrorRAG(
            503,

            "No fue posible completar la sincronización "
            "o recuperación de la evidencia.",
        ) from error

    except ValueError as error:

        raise ErrorRAG(
            409,

            "La evidencia recuperada no cumple "
            "el contrato esperado.",
        ) from error

    return resultados


def diagnostico_sin_ia(
    db,
    usuario,
    pregunta,
):
    """Diagnostico independiente del planificador Gemini.

    No pretende interpretar preguntas en lenguaje natural.
    Recupera conteos de las entidades disponibles.
    """

    conteos = {}

    try:

        for entidad in CATALOGO:

            if entidad.startswith("rdf_"):
                continue

            consulta = Consulta(
                entidad=entidad,

                operacion="contar",

                limite=1,
            )

            resultado = ejecutar_consulta_sql(
                db,
                usuario,
                preparar_consulta(
                    consulta,
                    lambda valor: valor,
                ),
            )

            conteos[entidad] = (
                resultado["filas"][0]["valor"]
            )

        semantica = _preparar_semantica(
            db,
            usuario,
        )

    except FusekiNoDisponible as error:

        raise ErrorRAG(
            503,
            "Fuseki no está disponible.",
        ) from error

    except EvidenciaSemanticaInvalida as error:

        raise ErrorRAG(
            409,
            "No se obtuvo evidencia semántica válida.",
        ) from error

    except (SQLAlchemyError, RuntimeError) as error:

        raise ErrorRAG(
            503,
            "No fue posible completar el diagnóstico.",
        ) from error

    return {
        "pregunta": pregunta,

        "alcance": (
            "Diagnóstico general de fuentes sin IA. "
            "No interpreta ni responde la pregunta escrita."
        ),

        "periodo": None,

        "moneda": "COP",

        "postgresql": {
            "conteos": serializar(conteos),
        },

        "fuseki": semantica,

        "catalogo": CATALOGO,

        "fuentes": [
            {
                "origen": "PostgreSQL",
                "tipo": "Conteos de entidades",
            },
            {
                "origen": "Fuseki/SPARQL",
                "tipo": "Metadatos de la instantánea RDF",
            },
        ],

        "limitaciones": [
            "Este diagnóstico no utiliza Gemini.",
            "Los conteos incluyen los estados registrados.",
            "No incluye operaciones offline pendientes.",
        ],
    }