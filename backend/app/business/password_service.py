import hashlib
import logging
import secrets

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from functools import partial

from app.business.errores import (
    CodigoError,
    ErrorNegocio,
)

from app.persistence import (
    password_repository as repo,
)

from app.persistence import (
    limite_recuperacion_repository as limite_repo,
)

from app.persistence.usuario_repository import (
    buscar_usuario_por_email,
)

from app.services.auth_service import (
    generar_hash,
    verificar_password,
)

from app.services import (
    correo_recuperacion_service as correo,
)


logger = logging.getLogger(__name__)

VIGENCIA = timedelta(minutes=15)

ESPERA = timedelta(minutes=1)

MAX_SOLICITUDES = 5


def _ahora():

    return datetime.now(timezone.utc)


def _huella(token):

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def _error_token():

    return ErrorNegocio(
        CodigoError.VALIDACION,

        "Enlace invalido, vencido o utilizado.",
    )


def _nueva(datos):

    nueva = datos.nueva_password.get_secret_value()

    if nueva != datos.confirmacion_password.get_secret_value():

        raise ErrorNegocio(
            CodigoError.VALIDACION,

            "Las contrasenas no coinciden.",
        )

    return nueva


def _coincide(password, hash_guardado):

    try:

        return verificar_password(
            password,
            hash_guardado,
        )

    except Exception:

        return False


def _guardar(db, usuario, nueva):

    if _coincide(
        nueva,
        usuario.password_hash,
    ):

        raise ErrorNegocio(
            CodigoError.VALIDACION,

            "Elige una contrasena diferente.",
        )

    repo.actualizar_password(
        db,
        usuario,
        generar_hash(nueva),
    )

    db.commit()


def _entregar(config, email, token):

    try:

        correo.enviar_enlace(
            config,
            email,
            token,
        )

    except Exception:

        logger.warning(
            "No fue posible enviar "
            "un correo de recuperacion"
        )


# ========================================
# SOLICITAR RECUPERACION
# ========================================

MAX_GLOBAL_15_MINUTOS = 20

MAX_GLOBAL_24_HORAS = 200


def _controlar_limite_global(db):

    try:

        permitido = limite_repo.reservar_cupo(
            db,

            MAX_GLOBAL_15_MINUTOS,

            MAX_GLOBAL_24_HORAS,
        )

        if permitido:

            db.commit()

        else:

            db.rollback()

    except Exception as error:

        db.rollback()

        logger.warning(
            "Recuperacion: control global no disponible"
        )

        raise ErrorNegocio(
            CodigoError.FUENTE_NO_DISPONIBLE,

            "Recuperacion temporalmente no disponible.",
        ) from error

    if not permitido:

        raise ErrorNegocio(
            CodigoError.LIMITE_SOLICITUDES,

            "Limite de solicitudes alcanzado. Intenta mas tarde.",
        )


def solicitar_recuperacion(db, email):

    try:

        config = correo.obtener_configuracion()

    except correo.CorreoNoDisponible as error:

        raise ErrorNegocio(
            CodigoError.FUENTE_NO_DISPONIBLE,

            "Recuperacion temporalmente no disponible.",
        ) from error

    _controlar_limite_global(db)

    try:

        usuario = buscar_usuario_por_email(
            db,
            email,
        )

        if usuario is None:

            db.rollback()

            return None

        usuario = repo.bloquear_usuario_auth(
            db,
            usuario.id_usuario,
        )

        if usuario is None:

            db.rollback()

            return None

        ahora = _ahora()

        ultima, cantidad = (
            repo.ultima_expiracion_y_cantidad(
                db,
                usuario.id_usuario,
                ahora,
            )
        )

        if (
            cantidad >= MAX_SOLICITUDES

            or (
                ultima

                and ultima > ahora + VIGENCIA - ESPERA
            )
        ):

            db.rollback()

            return None

        token = secrets.token_urlsafe(32)

        destinatario = usuario.email

        repo.insertar_token(
            db,

            usuario.id_usuario,

            _huella(token),

            ahora + VIGENCIA,
        )

        db.commit()

        return partial(
            _entregar,

            config,

            destinatario,

            token,
        )

    except Exception:

        db.rollback()

        raise


# ========================================
# CAMBIAR CONTRASENA
# ========================================

def cambiar_contrasena(
    db,
    uid,
    version,
    datos,
):

    try:

        nueva = _nueva(datos)

        usuario = repo.bloquear_usuario_auth(
            db,
            uid,
        )

        if (
            usuario is None

            or usuario.version_sesion != version
        ):

            raise ErrorNegocio(
                CodigoError.AUTENTICACION_REQUERIDA,

                "Inicia sesion nuevamente.",
            )

        if not _coincide(
            datos.password_actual.get_secret_value(),

            usuario.password_hash,
        ):

            raise ErrorNegocio(
                CodigoError.VALIDACION,

                "La contrasena actual no es correcta.",
            )

        _guardar(
            db,
            usuario,
            nueva,
        )

    except Exception:

        db.rollback()

        raise


# ========================================
# RESTABLECER CONTRASENA
# ========================================

def restablecer_contrasena(db, datos):

    try:

        nueva = _nueva(datos)

        huella = _huella(datos.token)

        uid = repo.propietario_token(
            db,
            huella,
        )

        if uid is None:

            raise _error_token()

        usuario = repo.bloquear_usuario_auth(
            db,
            uid,
        )

        if usuario is None:

            raise _error_token()

        token = repo.bloquear_token(
            db,
            uid,
            huella,
        )

        if (
            token is None

            or token.usado

            or token.fecha_expiracion <= _ahora()
        ):

            raise _error_token()

        _guardar(
            db,
            usuario,
            nueva,
        )

    except Exception:

        db.rollback()

        raise