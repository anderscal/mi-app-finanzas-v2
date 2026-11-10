
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
