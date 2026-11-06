from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.auth_schema import (
    TokenRespuesta,
    UsuarioRegistro,
    UsuarioRespuesta,
)

from app.services.auth_service import (
    autenticar_usuario,
    crear_access_token,
    registrar_usuario,
)

from app.business.cuenta_service import (
    consultar_resumen_cuentas,
)


router = APIRouter(
    prefix="/auth",
    tags=["Autenticación"]
)


@router.post(
    "/registro",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_201_CREATED
)
def registro(
    datos: UsuarioRegistro,
    db: SesionBD
):
    return registrar_usuario(
        db,
        datos
    )


@router.post(
    "/login",
    response_model=TokenRespuesta
)
def login(
    db: SesionBD,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    usuario = autenticar_usuario(
        db,
        form_data.username,
        form_data.password
    )

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    token = crear_access_token(
        usuario.id_usuario
    )

    return TokenRespuesta(
        access_token=token,
        token_type="bearer"
    )


@router.get(
    "/me",
    response_model=UsuarioRespuesta
)
def mi_perfil(
    usuario: UsuarioActual
):
    return usuario


@router.get("/mis-cuentas")
def mis_cuentas(
    db: SesionBD,
    usuario: UsuarioActual
):
    return consultar_resumen_cuentas(
        db=db,
        id_usuario=usuario.id_usuario
    )