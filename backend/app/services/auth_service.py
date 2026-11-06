
import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Usuario
from app.persistence.database import get_db
from app.persistence.usuario_repository import (
    buscar_usuario_por_email,
    buscar_usuario_por_id,
)
from app.schemas.auth_schema import UsuarioRegistro


load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))

if not SECRET_KEY or len(SECRET_KEY) < 64:
    raise RuntimeError(
        "Configura una JWT_SECRET_KEY aleatoria de 64 caracteres hexadecimales"
    )

if os.getenv("JWT_ALGORITHM", "HS256") != ALGORITHM:
    raise RuntimeError("JWT_ALGORITHM debe ser HS256")

if EXPIRE_MINUTES <= 0:
    raise RuntimeError("JWT_EXPIRE_MINUTES debe ser positivo")


password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login"
)


def generar_hash(password: str) -> str:
    return password_hash.hash(password)


def verificar_password(
    password: str,
    hash_guardado: str
) -> bool:
    return password_hash.verify(
        password,
        hash_guardado
    )


def registrar_usuario(
    db: Session,
    datos: UsuarioRegistro
):
    email = str(datos.email).strip().lower()

    if buscar_usuario_por_email(db, email):
        raise HTTPException(
            status_code=409,
            detail="El correo ya está registrado"
        )

    usuario = Usuario(
        nombre_1=datos.nombre_1.strip(),
        nombre_2=datos.nombre_2,
        apellido_1=datos.apellido_1.strip(),
        apellido_2=datos.apellido_2,
        email=email,
        password_hash=generar_hash(datos.password)
    )

    try:
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No fue posible registrar ese correo"
        )

    return usuario


def autenticar_usuario(
    db: Session,
    email: str,
    password: str
):
    usuario = buscar_usuario_por_email(db, email)

    if usuario is None:
        return None

    try:
        valido = verificar_password(
            password,
            usuario.password_hash
        )
    except Exception:
        # Un hash de pruebas puede no tener
        # un formato reconocido por Argon2.
        return None

    if not valido:
        return None

    return usuario


def crear_access_token(id_usuario: int) -> str:
    ahora = datetime.now(timezone.utc)

    payload = {
        "sub": str(id_usuario),
        "iat": ahora,
        "exp": ahora + timedelta(
            minutes=EXPIRE_MINUTES
        )
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def obtener_usuario_actual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    error_credenciales = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar la autenticación",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={
                "require": ["sub", "exp", "iat"]
            }
        )

        sub = payload.get("sub")

        if not isinstance(sub, str):
            raise error_credenciales

        id_usuario = int(sub)

        if id_usuario <= 0:
            raise error_credenciales

    except (InvalidTokenError, ValueError, TypeError):
        raise error_credenciales

    usuario = buscar_usuario_por_id(
        db,
        id_usuario
    )

    if usuario is None:
        raise error_credenciales

    return usuario
