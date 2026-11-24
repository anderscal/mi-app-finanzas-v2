"""Endpoints del asistente financiero. Presentation."""

from fastapi import APIRouter, HTTPException

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.rag_schema import (
    PreguntaRAG,
    PreguntaConIA,
)

from app.business.rag_service import (
    ErrorRAG,
    consultar_diagnostico,
    responder_asistente,
)


router = APIRouter(
    prefix="/asistente",
    tags=["Asistente RAG"],
)


@router.post("/contexto")
def consultar_contexto(
    datos: PreguntaRAG,

    db: SesionBD,

    usuario: UsuarioActual,
):

    try:

        return consultar_diagnostico(
            db,

            usuario.id_usuario,

            datos.pregunta,
        )

    except ErrorRAG as error:

        raise HTTPException(
            status_code=error.codigo,

            detail=str(error),
        ) from error


@router.post("/preguntar")
def responder_con_rag(
    datos: PreguntaConIA,

    db: SesionBD,

    usuario: UsuarioActual,
):

    try:

        return responder_asistente(
            db,

            usuario.id_usuario,

            datos.pregunta,

            datos.autorizo_envio_ia,
        )

    except ErrorRAG as error:

        raise HTTPException(
            status_code=error.codigo,

            detail=str(error),
        ) from error