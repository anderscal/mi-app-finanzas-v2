"""Repositorio de usuarios.

Capa Persistence.

No contiene reglas de autenticacion ni respuestas HTTP.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Usuario


def buscar_usuario_por_email(
    db: Session,
    email: str,
):

    email_normalizado = (
        email.strip().lower()
    )

    consulta = select(Usuario).where(
        func.lower(
            func.trim(Usuario.email)
        )
        == email_normalizado
    )

    return db.scalar(consulta)


def buscar_usuario_por_id(
    db: Session,
    id_usuario: int,
):

    return db.get(
        Usuario,
        id_usuario,
    )


def insertar_usuario(
    db: Session,
    *,
    nombre_1: str,
    nombre_2: str | None,
    apellido_1: str,
    apellido_2: str | None,
    email: str,
    password_hash: str,
):

    usuario = Usuario(
        nombre_1=nombre_1,
        nombre_2=nombre_2,
        apellido_1=apellido_1,
        apellido_2=apellido_2,
        email=email,
        password_hash=password_hash,
    )

    db.add(usuario)

    return usuario


def refrescar_usuario(
    db: Session,
    usuario: Usuario,
):

    db.refresh(usuario)

    return usuario


def bloquear_usuario(
    db: Session,
    id_usuario: int,
):
    """Serializa operaciones concurrentes del mismo usuario.

    No confirma la transaccion.
    """

    consulta = (
        select(Usuario)
        .where(
            Usuario.id_usuario == id_usuario
        )
        .with_for_update()
    )

    return db.scalar(consulta)