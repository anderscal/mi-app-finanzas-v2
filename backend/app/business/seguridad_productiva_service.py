import hashlib
import hmac
import os

from app.business.errores import (
    CodigoError,
    ErrorNegocio,
)

from app.business.auth_business_service import (
    iniciar_sesion,
    registrar_usuario,
)

from app.business.rag_service import (
    responder_asistente,
    ErrorRAG,
)

from app.persistence import (
    limite_operacion_repository as repo,
)

from app.services.auth_service import (
    SECRET_KEY,
)


# Orden:
# global 15 minutos
# global 24 horas
# sujeto 15 minutos
# sujeto 24 horas

LIMITES = {
    "login": (60, 500, 8, 500),
    "registro": (15, 40, 15, 40),
    "rag": (6, 12, 3, 6),
}


def _huella(operacion, valor):

    return hmac.new(

        SECRET_KEY.encode("utf-8"),

        (
            "limite-v1:"
            + operacion
            + ":"
            + valor
        ).encode("utf-8"),

        hashlib.sha256,

    ).hexdigest()


def _controlar(db, operacion, valor):

    try:

        permitido = repo.reservar(

            db,

            operacion,

            _huella(operacion, valor),

            LIMITES[operacion],
        )

        if permitido:

            db.commit()

        else:

            db.rollback()

    except Exception:

        db.rollback()

        raise ErrorNegocio(

            CodigoError.FUENTE_NO_DISPONIBLE,

            "Servicio temporalmente no disponible.",

        ) from None

    if not permitido:

        raise ErrorNegocio(

            CodigoError.LIMITE_SOLICITUDES,

            "Limite de solicitudes alcanzado.",
        )


# ======================================
# LOGIN PROTEGIDO
# ======================================

def iniciar_sesion_protegida(
    db,
    email,
    password,
):

    normalizado = email.strip().lower()

    _controlar(
        db,
        "login",
        normalizado,
    )

    if (
        not normalizado

        or len(normalizado) > 254

        or not password

        or len(password) > 128
    ):

        raise ErrorNegocio(

            CodigoError.AUTENTICACION_REQUERIDA,

            "Credenciales incorrectas",
        )

    return iniciar_sesion(
        db,
        normalizado,
        password,
    )


# ======================================
# REGISTRO PROTEGIDO
# ======================================

def registrar_protegido(db, datos):

    _controlar(
        db,
        "registro",
        "global",
    )

    return registrar_usuario(
        db,
        datos,
    )


# ======================================
# AUTORIZACION DEMO
# ======================================

def _demo_autorizada(uid):

    valores = os.getenv(
        "RAG_DEMO_USUARIOS",
        "",
    ).strip().split(",")

    valores = [
        v.strip()
        for v in valores
    ]

    if any(
        not v.isascii()
        or not v.isdecimal()
        for v in valores
    ):

        return False

    return (

        type(uid) is int

        and uid > 0

        and str(uid) in valores
    )


# ======================================
# RAG PROTEGIDO
# ======================================

def responder_demo(
    db,
    uid,
    pregunta,
    autorizo,
):

    if autorizo is not True:

        raise ErrorRAG(

            403,

            "Autoriza el envio a Gemini.",
        )

    if os.getenv(
        "RAG_IA_HABILITADA",
        "0",
    ) != "1":

        raise ErrorRAG(

            503,

            "Asistente no habilitado.",
        )

    if not _demo_autorizada(uid):

        raise ErrorRAG(

            403,

            "Asistente reservado a cuentas de demostracion.",
        )

    _controlar(
        db,
        "rag",
        str(uid),
    )

    return responder_asistente(

        db,

        uid,

        pregunta,

        autorizo,
    )