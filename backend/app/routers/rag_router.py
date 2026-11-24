
"""Endpoints autenticados del asistente RAG.

Paso 27.7.1:
- Presentacion financiera pertinente.
- Respuestas verificables.
- Respaldo general sin Gemini.
"""

import logging
import os

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from sqlalchemy.exc import SQLAlchemyError

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.rag_schema import (
    PreguntaRAG,
    PreguntaConIA,
)

from app.business.rag_intencion import (
    interpretar_pregunta,
)

from app.business.rag_retrieval_service import (
    construir_contexto_rag,
)

from app.business.rag_relaciones_276 import (
    enriquecer_contexto_276,
)

from app.business.rag_motor_respuestas import (
    PlanRespuestaInvalido,
)

from app.business.rag_presentacion_pertinente import (
    generar_respuesta_pertinente as generar_respuesta_rag,

    generar_respuesta_local_pertinente as generar_respuesta_local,
)

from app.services.fuseki_client import (
    FusekiNoDisponible,
)

from app.services.rag_ia_service import (
    IANoDisponible,
    modelo_gemini,
)

from app.services.semantica_auto_sync import (
    asegurar_actualizacion_para_rag,
)


router = APIRouter(
    prefix="/asistente",
    tags=["Asistente RAG"],
)

logger = logging.getLogger(__name__)


def evaluar_vigencia_rdf(
    fecha_texto: str | None,
    ahora: datetime | None = None,
) -> dict:

    desconocida = {
        "estado": "DESCONOCIDA",
        "antiguedad_horas": None,
    }

    if not isinstance(fecha_texto, str):
        return desconocida

    try:

        fecha = datetime.fromisoformat(
            fecha_texto.replace("Z", "+00:00")
        )

    except (
        ValueError,
        TypeError,
        OverflowError,
    ):
        return desconocida

    if fecha.tzinfo is None:
        return desconocida

    referencia = (
        ahora or datetime.now(timezone.utc)
    )

    if referencia.tzinfo is None:
        return desconocida

    horas = (
        referencia.astimezone(timezone.utc)
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
            horas,
            2,
        ),
    }


def _anotar_vigencia_contexto(
    contexto: dict,
    ahora: datetime | None = None,
) -> dict:

    semantica = contexto.get(
        "fuseki"
    )

    if not isinstance(semantica, dict):
        return contexto

    vigencia = evaluar_vigencia_rdf(
        semantica.get("fecha_instantanea"),
        ahora,
    )

    estado = vigencia["estado"]

    mensajes = {

        "RECIENTE": (
            "La instantánea RDF tiene como máximo "
            "24 horas, pero podría no incluir "
            "movimientos posteriores a su publicación."
        ),

        "ANTIGUA": (
            "La instantánea RDF tiene más de "
            "24 horas. No debe utilizarse para "
            "afirmar el estado financiero actual."
        ),

        "DESCONOCIDA": (
            "No fue posible comprobar la fecha "
            "de publicación de la instantánea RDF."
        ),
    }

    advertencia = mensajes[estado]

    semantica["vigencia"] = estado

    semantica["antiguedad_horas"] = (
        vigencia["antiguedad_horas"]
    )

    semantica["advertencia"] = (
        f"{str(semantica.get('advertencia') or '').strip()} "
        f"{advertencia}"
    ).strip()

    for fuente in contexto.get(
        "fuentes", []
    ):

        if (
            isinstance(fuente, dict)

            and fuente.get("origen")
            == "Fuseki/SPARQL"
        ):

            fuente["vigencia"] = estado

            fuente["antiguedad_horas"] = (
                vigencia["antiguedad_horas"]
            )

    limitaciones = contexto.get(
        "limitaciones"
    )

    if isinstance(limitaciones, list):

        if advertencia not in limitaciones:

            limitaciones.append(
                advertencia
            )

    return contexto


def _validar_intencion(
    pregunta: str,
):

    intencion = interpretar_pregunta(
        pregunta
    )

    if not intencion.temas:

        raise HTTPException(
            status_code=422,

            detail=(
                intencion.aviso
                or "Indica qué información financiera necesitas."
            ),
        )


def _recuperar(
    db,
    id_usuario,
    pregunta,
):

    try:

        asegurar_actualizacion_para_rag(
            db,
            id_usuario,
        )

        contexto = construir_contexto_rag(
            db,
            id_usuario,
            pregunta,
        )

        contexto = enriquecer_contexto_276(
            db,
            id_usuario,
            contexto,
        )

        return _anotar_vigencia_contexto(
            contexto
        )

    except FusekiNoDisponible as error:

        raise HTTPException(
            status_code=503,

            detail=(
                "Fuseki no está disponible; "
                "PostgreSQL conserva tus datos."
            ),
        ) from error

    except (
        RuntimeError,
        SQLAlchemyError,
    ) as error:

        raise HTTPException(
            status_code=503,

            detail=(
                "No fue posible recuperar el contexto "
                "financiero y semántico. "
                "No se modificaron datos financieros."
            ),
        ) from error


def _respuesta_respaldo(
    pregunta: str,
    contexto: dict,
    motivo: str,
) -> dict:

    respuesta = generar_respuesta_local(
        pregunta,
        contexto,
        motivo=motivo,
    )

    return {
        "pregunta": pregunta,

        "respuesta": respuesta,

        "metodo": "CALCULO_SQL_RESPALDO",

        "proveedor": "FastAPI/PostgreSQL",

        "modelo": None,

        "periodo": contexto.get(
            "periodo", {}
        ),

        "fuentes": [{
            "origen": "PostgreSQL",

            "tipo": (
                "Evidencia financiera recuperada "
                "del usuario autenticado"
            ),
        }],

        "limitaciones": [
            (
                "Respuesta construida localmente; "
                "no generada por Gemini."
            ),
            (
                "No se utilizan comprobaciones RDF "
                "para afirmar consistencia semántica "
                "en este modo de respaldo."
            ),
            (
                "No incluye operaciones offline "
                "pendientes de sincronizar."
            ),
        ],
    }


@router.post("/contexto")
def consultar_contexto(
    datos: PreguntaRAG,
    db: SesionBD,
    usuario: UsuarioActual,
):

    _validar_intencion(
        datos.pregunta
    )

    return _recuperar(
        db,
        usuario.id_usuario,
        datos.pregunta,
    )


@router.post("/preguntar")
def responder_con_rag(
    datos: PreguntaConIA,
    db: SesionBD,
    usuario: UsuarioActual,
):

    if not datos.autorizo_envio_ia:

        raise HTTPException(
            403,

            "Debes autorizar el envío del "
            "contexto financiero a Gemini.",
        )

    if os.getenv(
        "RAG_IA_HABILITADA",
        "0",
    ) != "1":

        raise HTTPException(
            503,

            "El proveedor de IA todavía "
            "no está habilitado.",
        )

    if not os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip():

        raise HTTPException(
            503,

            "Falta configurar GEMINI_API_KEY "
            "en el backend.",
        )

    _validar_intencion(
        datos.pregunta
    )

    try:

        modelo = modelo_gemini()

    except IANoDisponible as error:

        raise HTTPException(
            error.codigo_http,
            str(error),
        ) from error

    # Se mantiene una sola recuperacion
    # por solicitud.

    contexto = _recuperar(
        db,
        usuario.id_usuario,
        datos.pregunta,
    )

    try:

        respuesta = generar_respuesta_rag(
            datos.pregunta,
            contexto,
        )

    except PlanRespuestaInvalido:

        logger.warning(
            "Plan Gemini rechazado; "
            "se activa el resumen financiero local."
        )

        return _respuesta_respaldo(
            datos.pregunta,
            contexto,

            motivo=(
                "La respuesta de Gemini no superó "
                "la validación estructural."
            ),
        )

    except IANoDisponible as error:

        if (
            error.transitorio
            or error.codigo_http == 429
        ):

            logger.warning(
                "Respaldo financiero local | HTTP=%s",
                error.codigo_http,
            )

            return _respuesta_respaldo(
                datos.pregunta,
                contexto,

                motivo=(
                    "Gemini no está disponible "
                    "o alcanzó temporalmente "
                    "su límite de solicitudes."
                ),
            )

        raise HTTPException(
            error.codigo_http,
            str(error),
        ) from error

    return {
        "pregunta": datos.pregunta,

        "respuesta": respuesta,

        "metodo": "RAG_SQL_SPARQL",

        "proveedor": "Google Gemini",

        "modelo": modelo,

        "periodo": contexto["periodo"],

        "fuentes": contexto["fuentes"],

        "limitaciones": [
            *contexto["limitaciones"],
            (
                "Business determina los temas y filtros; "
                "Gemini organiza las secciones permitidas "
                "sin generar los valores financieros."
            ),
        ],
    }
