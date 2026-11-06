from fastapi import APIRouter

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.movimiento_schema import (
    AnulacionMovimientoRespuesta,
    MovimientoNormalCrear,
    RegistroMovimientoRespuesta,
)

from app.business.movimiento_escritura_service import (
    registrar_movimiento_normal,
)

from app.business.anulacion_service import (
    anular_movimiento,
)


router = APIRouter(
    prefix="/movimientos",
    tags=["Movimientos"]
)


@router.post(
    "/normales",
    response_model=RegistroMovimientoRespuesta
)
def crear_movimiento_normal(
    datos: MovimientoNormalCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return registrar_movimiento_normal(
        db=db,
        id_usuario=usuario.id_usuario,
        datos=datos
    )


@router.post(
    "/{id_movimiento}/anular",
    response_model=AnulacionMovimientoRespuesta
)
def anular_movimiento_endpoint(
    id_movimiento: int,
    db: SesionBD,
    usuario: UsuarioActual
):
    return anular_movimiento(
        db=db,
        id_usuario=usuario.id_usuario,
        id_movimiento=id_movimiento
    )