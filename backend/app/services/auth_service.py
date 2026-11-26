"""Servicio tecnico de autenticacion.

Capa Services.

Responsabilidades:
- Hashing de contrasenas.
- Verificacion de contrasenas.
- Generacion y validacion de JWT.

No consulta bases de datos.
No depende de Business ni de FastAPI.
"""

import os

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import jwt

from dotenv import load_dotenv

from jwt.exceptions import InvalidTokenError

from pwdlib import PasswordHash


load_dotenv()


SECRET_KEY = os.getenv("JWT_SECRET_KEY")

ALGORITHM = "HS256"

EXPIRE_MINUTES = int(
    os.getenv("JWT_EXPIRE_MINUTES", "30")
)


if not SECRET_KEY or len(SECRET_KEY) < 64:

    raise RuntimeError(
        "Configura una JWT_SECRET_KEY aleatoria "
        "de 64 caracteres hexadecimales"
    )


if os.getenv("JWT_ALGORITHM", "HS256") != ALGORITHM:

    raise RuntimeError(
        "JWT_ALGORITHM debe ser HS256"
    )


if EXPIRE_MINUTES <= 0:

    raise RuntimeError(
        "JWT_EXPIRE_MINUTES debe ser positivo"
    )


password_hash = PasswordHash.recommended()


class TokenInvalido(Exception):

    """El JWT no es valido o ha expirado."""


def generar_hash(password: str) -> str:

    return password_hash.hash(password)


def verificar_password(
    password: str,
    hash_guardado: str,
) -> bool:

    return password_hash.verify(
        password,
        hash_guardado,
    )


def crear_access_token(
    id_usuario: int,
    version_sesion: int = 0,
) -> str:

    if type(id_usuario) is not int or id_usuario <= 0:

        raise ValueError(
            "Identificador de usuario invalido"
        )

    if type(version_sesion) is not int or version_sesion < 0:
        raise ValueError("Version de sesion invalida")

    ahora = datetime.now(timezone.utc)

    payload = {
        "sub": str(id_usuario),
        "ver": version_sesion,

        "iat": ahora,

        "exp": ahora + timedelta(
            minutes=EXPIRE_MINUTES
        ),
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def validar_sesion_token(
    token: str,
) -> tuple[int, int]:

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],

            options={
                "require": [
                    "sub",
                    "exp",
                    "iat",
                    "ver",
                ],
            },
        )

        sub = payload.get("sub")

        if not isinstance(sub, str):

            raise TokenInvalido(
                "Identificador del token invalido"
            )

        id_usuario = int(sub)

        if id_usuario <= 0:

            raise TokenInvalido(
                "Identificador del token invalido"
            )

        version = payload["ver"]

        if type(version) is not int or version < 0:
            raise TokenInvalido("Version de sesion invalida")

        return id_usuario, version

    except (
        InvalidTokenError,
        ValueError,
        TypeError,
    ) as error:

        raise TokenInvalido(
            "Token invalido o expirado"
        ) from error

def validar_access_token(token: str) -> int:

    return validar_sesion_token(token)[0]
