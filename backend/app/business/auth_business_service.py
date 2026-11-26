"""Casos de uso de autenticacion.

Capa Business.

Coordina Services y Persistence.
No depende de FastAPI.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.business.errores import (
    CodigoError,
    ErrorNegocio,
)

from app.persistence.usuario_repository import (
    buscar_usuario_por_email,
    buscar_usuario_por_id,
    insertar_usuario,
    refrescar_usuario,
)

from app.schemas.auth_schema import (
    UsuarioRegistro,
)

from app.services.auth_service import (
    TokenInvalido,
    generar_hash,
    verificar_password,
    crear_access_token,
    validar_sesion_token,
)


def registrar_usuario(
    db: Session,
    datos: UsuarioRegistro,
):

    email = str(
        datos.email
    ).strip().lower()

    if buscar_usuario_por_email(
        db,
        email,
    ):

        raise ErrorNegocio(
            CodigoError.CONFLICTO,

            "El correo ya está registrado",
        )

    hash_guardado = generar_hash(
        datos.password
    )

    try:

        usuario = insertar_usuario(
            db,

            nombre_1=datos.nombre_1.strip(),

            nombre_2=datos.nombre_2,

            apellido_1=datos.apellido_1.strip(),

            apellido_2=datos.apellido_2,

            email=email,

            password_hash=hash_guardado,
        )

        db.commit()

        refrescar_usuario(
            db,
            usuario,
        )

    except IntegrityError as error:

        db.rollback()

        raise ErrorNegocio(
            CodigoError.CONFLICTO,

            "No fue posible registrar ese correo",
        ) from error

    return usuario


def autenticar_usuario(
    db: Session,
    email: str,
    password: str,
):

    usuario = buscar_usuario_por_email(
        db,
        email,
    )

    if usuario is None:
        return None

    try:

        valido = verificar_password(
            password,
            usuario.password_hash,
        )

    except Exception:

        # Conserva el comportamiento anterior
        # ante un hash almacenado no reconocido.

        return None

    if not valido:
        return None

    return usuario


def iniciar_sesion(
    db: Session,
    email: str,
    password: str,
) -> str:

    usuario = autenticar_usuario(
        db,
        email,
        password,
    )

    if usuario is None:

        raise ErrorNegocio(
            CodigoError.AUTENTICACION_REQUERIDA,

            "Credenciales incorrectas",
        )

    return crear_access_token(
        usuario.id_usuario,
        usuario.version_sesion,
    )


def obtener_usuario_actual(
    token: str,
    db: Session,
):

    try:

        id_usuario, version = validar_sesion_token(
            token
        )

    except TokenInvalido as error:

        raise ErrorNegocio(
            CodigoError.AUTENTICACION_REQUERIDA,

            "No se pudo validar la autenticación",
        ) from error

    usuario = buscar_usuario_por_id(
        db,
        id_usuario,
    )

    if usuario is None or usuario.version_sesion != version:

        raise ErrorNegocio(
            CodigoError.AUTENTICACION_REQUERIDA,

            "No se pudo validar la autenticación",
        )

    return usuario