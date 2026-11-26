"""Dependencias de la interfaz HTTP.

Capa Presentation.

Inyeccion de sesiones y autenticacion de solicitudes.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy.orm import Session

from app.models import Usuario

from app.persistence.database import get_db

from app.business.auth_business_service import (
    obtener_usuario_actual as resolver_usuario,
)


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login"
)


SesionBD = Annotated[
    Session,

    Depends(get_db),
]


TokenBearer = Annotated[
    str,

    Depends(oauth2_scheme),
]


def obtener_usuario_actual(
    token: TokenBearer,

    db: SesionBD,
):

    return resolver_usuario(
        token=token,
        db=db,
    )


UsuarioActual = Annotated[
    Usuario,

    Depends(obtener_usuario_actual),
]   