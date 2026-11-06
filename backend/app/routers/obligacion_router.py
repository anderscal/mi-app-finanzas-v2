from fastapi import APIRouter

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.movimiento_schema import (
    AbonoObligacionCrear,
    AbonoObligacionRespuesta,
)

from app.business.obligacion_escritura_service import (
    registrar_abono_obligacion,
)


router = APIRouter(
    prefix="/obligaciones",
    tags=["Obligaciones"]
)


@router.post(
    "/abonos",
    response_model=AbonoObligacionRespuesta
)
def crear_abono_obligacion(
    datos: AbonoObligacionCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return registrar_abono_obligacion(
        db=db,
        id_usuario=usuario.id_usuario,
        datos=datos
    )