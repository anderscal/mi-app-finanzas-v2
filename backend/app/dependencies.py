from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.models import Usuario
from app.persistence.database import get_db
from app.services.auth_service import obtener_usuario_actual


SesionBD = Annotated[
    Session,
    Depends(get_db)
]

UsuarioActual = Annotated[
    Usuario,
    Depends(obtener_usuario_actual)
]