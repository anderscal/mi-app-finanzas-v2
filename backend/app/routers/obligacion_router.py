
from fastapi import APIRouter, status

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.movimiento_schema import (
    AbonoObligacionCrear,
    AbonoObligacionRespuesta,
)

from app.schemas.obligacion_schema import (
    ObligacionCrear,
    ObligacionActualizar,
    ObligacionRespuesta,
)

from app.business.obligacion_escritura_service import (
    registrar_abono_obligacion,
)

from app.business.obligacion_admin_service import (
    consultar_detalle_obligacion,
    crear_obligacion_financiera,
    actualizar_obligacion_financiera,
    desactivar_obligacion_financiera,
)


router = APIRouter(
    prefix="/obligaciones",
    tags=["Obligaciones"]
)


@router.post(
    "/",
    response_model=ObligacionRespuesta,
    status_code=status.HTTP_201_CREATED
)
def crear_obligacion(
    datos: ObligacionCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return crear_obligacion_financiera(
        db=db,
        id_usuario=usuario.id_usuario,
        datos=datos
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


@router.get(
    "/{id_obligacion}",
    response_model=ObligacionRespuesta
)
def detalle_obligacion(
    id_obligacion: int,
    db: SesionBD,
    usuario: UsuarioActual
):
    return consultar_detalle_obligacion(
        db=db,
        id_usuario=usuario.id_usuario,
        id_obligacion=id_obligacion
    )


@router.patch(
    "/{id_obligacion}",
    response_model=ObligacionRespuesta
)
def actualizar_obligacion(
    id_obligacion: int,
    datos: ObligacionActualizar,
    db: SesionBD,
    usuario: UsuarioActual
):
    return actualizar_obligacion_financiera(
        db=db,
        id_usuario=usuario.id_usuario,
        id_obligacion=id_obligacion,
        datos=datos
    )


@router.post(
    "/{id_obligacion}/desactivar",
    response_model=ObligacionRespuesta
)
def desactivar_obligacion(
    id_obligacion: int,
    db: SesionBD,
    usuario: UsuarioActual
):
    return desactivar_obligacion_financiera(
        db=db,
        id_usuario=usuario.id_usuario,
        id_obligacion=id_obligacion
    )
