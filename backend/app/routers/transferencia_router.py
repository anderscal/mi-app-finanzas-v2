from fastapi import APIRouter

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.movimiento_schema import (
    TransferenciaCrear,
    TransferenciaRespuesta,
)

from app.business.transferencia_service import (
    registrar_transferencia,
)


router = APIRouter(
    prefix="/transferencias",
    tags=["Transferencias"]
)


@router.post(
    "/",
    response_model=TransferenciaRespuesta
)
def crear_transferencia(
    datos: TransferenciaCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return registrar_transferencia(
        db=db,
        id_usuario=usuario.id_usuario,
        datos=datos
    )