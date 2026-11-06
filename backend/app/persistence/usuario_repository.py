
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Usuario


def buscar_usuario_por_email(
    db: Session,
    email: str
):
    email_normalizado = email.strip().lower()

    consulta = select(Usuario).where(
        func.lower(func.trim(Usuario.email))
        == email_normalizado
    )

    return db.scalar(consulta)


def buscar_usuario_por_id(
    db: Session,
    id_usuario: int
):
    return db.get(Usuario, id_usuario)
