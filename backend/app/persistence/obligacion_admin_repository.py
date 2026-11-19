
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Movimiento,
    ObligacionFinanciera,
    Usuario,
)


def bloquear_usuario(
    db: Session,
    id_usuario: int
):
    consulta = (
        select(Usuario)
        .where(
            Usuario.id_usuario == id_usuario
        )
        .with_for_update()
    )

    return db.scalar(consulta)


def buscar_obligacion_duplicada(
    db: Session,
    id_usuario: int,
    nombre: str,
    tipo: str,
    id_excluir: int | None = None
):
    nombre_normalizado = func.lower(
        func.regexp_replace(
            func.trim(
                ObligacionFinanciera.nombre_obligacion
            ),
            "[[:space:]]+",
            " ",
            "g"
        )
    )

    consulta = (
        select(ObligacionFinanciera)
        .where(
            ObligacionFinanciera.id_usuario
            == id_usuario,
            ObligacionFinanciera.tipo_obligacion
            == tipo,
            nombre_normalizado == nombre.lower()
        )
    )

    if id_excluir is not None:
        consulta = consulta.where(
            ObligacionFinanciera.id_obligacion
            != id_excluir
        )

    return db.scalar(
        consulta.limit(1)
    )


def obtener_obligacion_usuario(
    db: Session,
    id_usuario: int,
    id_obligacion: int
):
    consulta = (
        select(ObligacionFinanciera)
        .where(
            ObligacionFinanciera.id_usuario
            == id_usuario,
            ObligacionFinanciera.id_obligacion
            == id_obligacion
        )
    )

    return db.scalar(consulta)


def bloquear_obligacion_usuario(
    db: Session,
    id_usuario: int,
    id_obligacion: int
):
    consulta = (
        select(ObligacionFinanciera)
        .where(
            ObligacionFinanciera.id_usuario
            == id_usuario,
            ObligacionFinanciera.id_obligacion
            == id_obligacion
        )
        .with_for_update()
    )

    return db.scalar(consulta)


def contar_abonos_activos(
    db: Session,
    id_obligacion: int
) -> int:
    consulta = (
        select(func.count(Movimiento.id_movimiento))
        .where(
            Movimiento.id_obligacion == id_obligacion,
            Movimiento.origen == "OBLIGACION",
            Movimiento.estado == "ACTIVO"
        )
    )

    return int(db.scalar(consulta) or 0)


def insertar_obligacion(
    db: Session,
    obligacion: ObligacionFinanciera
):
    db.add(obligacion)
    db.flush()

    return obligacion
