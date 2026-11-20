
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    MetaFinanciera,
    Usuario,
)


def bloquear_usuario_meta(
    db: Session,
    id_usuario: int
):
    return db.scalar(
        select(Usuario)
        .where(
            Usuario.id_usuario == id_usuario
        )
        .with_for_update()
    )


def listar_metas_usuario(
    db: Session,
    id_usuario: int
):
    consulta = (
        select(MetaFinanciera)
        .where(
            MetaFinanciera.id_usuario == id_usuario
        )
        .order_by(
            MetaFinanciera.id_meta.desc()
        )
    )

    return list(
        db.scalars(consulta).all()
    )


def obtener_meta_usuario(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    return db.scalar(
        select(MetaFinanciera)
        .where(
            MetaFinanciera.id_usuario == id_usuario,
            MetaFinanciera.id_meta == id_meta
        )
    )


def bloquear_meta_usuario(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    return db.scalar(
        select(MetaFinanciera)
        .where(
            MetaFinanciera.id_usuario == id_usuario,
            MetaFinanciera.id_meta == id_meta
        )
        .with_for_update()
    )


def buscar_meta_nombre(
    db: Session,
    id_usuario: int,
    nombre: str,
    id_excluir: int | None = None
):
    nombre_normalizado = func.lower(
        func.regexp_replace(
            func.trim(
                MetaFinanciera.nombre_meta
            ),
            "[[:space:]]+",
            " ",
            "g"
        )
    )

    consulta = (
        select(MetaFinanciera)
        .where(
            MetaFinanciera.id_usuario == id_usuario,
            nombre_normalizado == nombre.lower()
        )
    )

    if id_excluir is not None:
        consulta = consulta.where(
            MetaFinanciera.id_meta != id_excluir
        )

    return db.scalar(
        consulta.limit(1)
    )


def insertar_meta(
    db: Session,
    meta: MetaFinanciera
):
    db.add(meta)
    db.flush()

    return meta
