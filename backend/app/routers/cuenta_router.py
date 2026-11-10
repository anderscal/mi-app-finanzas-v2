from app.schemas.cuenta_schema import CuentaActualizar

from fastapi import (
    APIRouter,
    status,
)

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.cuenta_schema import (
    CuentaCrear,
    CuentaRespuesta,
)

from app.business.cuenta_service import (
    crear_cuenta_financiera,
    actualizar_cuenta_financiera,
    desactivar_cuenta_financiera,
)


router = APIRouter(
    prefix="/cuentas",
    tags=["Cuentas financieras"]
)


@router.post(
    "/",
    response_model=CuentaRespuesta,
    status_code=status.HTTP_201_CREATED
)
def crear_cuenta(
    datos: CuentaCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return crear_cuenta_financiera(
        db=db,
        id_usuario=usuario.id_usuario,
        datos=datos
    )

@router.patch(
    "/{id_cuenta}",
    response_model=CuentaRespuesta
)
def actualizar_cuenta(
    id_cuenta: int,
    datos: CuentaActualizar,
    db: SesionBD,
    usuario: UsuarioActual
):
    return actualizar_cuenta_financiera(
        db=db,
        id_usuario=usuario.id_usuario,
        id_cuenta=id_cuenta,
        datos=datos
    )


@router.post(
    "/{id_cuenta}/desactivar",
    response_model=CuentaRespuesta
)
def desactivar_cuenta(
    id_cuenta: int,
    db: SesionBD,
    usuario: UsuarioActual
):
    return desactivar_cuenta_financiera(
        db=db,
        id_usuario=usuario.id_usuario,
        id_cuenta=id_cuenta
    )
