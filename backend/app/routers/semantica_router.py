"""Endpoints semanticos autenticados.

Capa Presentation.
"""

from fastapi import APIRouter

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.business import (
    semantica_consulta_service as servicio,
)


router = APIRouter(
    prefix="/semantica",

    tags=[
        "Conocimiento semántico",
    ],
)


@router.post("/sincronizar")
def sincronizar_semantica(
    db: SesionBD,
    usuario: UsuarioActual,
):

    return servicio.sincronizar_semantica(
        db,
        usuario.id_usuario,
    )


@router.get("/cuentas")
def consultar_cuentas_semanticas(
    usuario: UsuarioActual,
):

    return servicio.consultar_cuentas_semanticas(
        usuario.id_usuario
    )