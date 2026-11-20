
from fastapi import (
    APIRouter,
    status,
)

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.presupuesto_schema import (
    PresupuestoCrear,
    PresupuestoActualizar,
    PresupuestoRespuesta,
)

from app.business.presupuesto_service import (
    consultar_presupuestos,
    crear_presupuesto_financiero,
    actualizar_presupuesto_financiero,
)


router = APIRouter(
    prefix="/presupuestos",
    tags=["Presupuestos financieros"]
)


@router.get(
    "/",
    response_model=list[PresupuestoRespuesta]
)
def listar_presupuestos(
    db: SesionBD,
    usuario: UsuarioActual
):
    return consultar_presupuestos(
        db=db,
        id_usuario=usuario.id_usuario
    )


@router.post(
    "/",
    response_model=PresupuestoRespuesta,
    status_code=status.HTTP_201_CREATED
)
def crear_presupuesto(
    datos: PresupuestoCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return crear_presupuesto_financiero(
        db=db,
        id_usuario=usuario.id_usuario,
        datos=datos
    )


@router.patch(
    "/{id_presupuesto}",
    response_model=PresupuestoRespuesta
)
def actualizar_presupuesto(
    id_presupuesto: int,
    datos: PresupuestoActualizar,
    db: SesionBD,
    usuario: UsuarioActual
):
    return actualizar_presupuesto_financiero(
        db=db,
        id_usuario=usuario.id_usuario,
        id_presupuesto=id_presupuesto,
        datos=datos
    )
