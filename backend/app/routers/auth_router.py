"""Endpoints de autenticacion.

Capa Presentation.
"""

from fastapi import (
    APIRouter,
    Depends,
    status,
)

from fastapi.security import (
    OAuth2PasswordRequestForm,
)

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.auth_schema import (
    TokenRespuesta,
    UsuarioRegistro,
    UsuarioRespuesta,
)

from app.business.auth_business_service import (
    registrar_usuario,
    iniciar_sesion,
)

from app.business.cuenta_service import (
    consultar_resumen_cuentas,
)


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"],
)


@router.post(
    "/registro",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_201_CREATED,
)
def registro(
    datos: UsuarioRegistro,

    db: SesionBD,
):

    return registrar_usuario(
        db,
        datos,
    )


@router.post(
    "/login",
    response_model=TokenRespuesta,
)
def login(
    db: SesionBD,

    form_data: OAuth2PasswordRequestForm = Depends(),
):

    token = iniciar_sesion(
        db,

        form_data.username,

        form_data.password,
    )

    return TokenRespuesta(
        access_token=token,
        token_type="bearer",
    )


@router.get(
    "/me",
    response_model=UsuarioRespuesta,
)
def mi_perfil(
    usuario: UsuarioActual,
):

    return usuario


@router.get("/mis-cuentas")
def mis_cuentas(
    db: SesionBD,

    usuario: UsuarioActual,
):

    return consultar_resumen_cuentas(
        db=db,

        id_usuario=usuario.id_usuario,
    )