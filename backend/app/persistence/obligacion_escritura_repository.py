from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CuentaFinanciera,
    Movimiento,
    ObligacionFinanciera,
)


def bloquear_obligacion(
    db: Session,
    id_obligacion: int,
    id_usuario: int
):
    consulta = (
        select(ObligacionFinanciera)
        .where(
            ObligacionFinanciera.id_obligacion
            == id_obligacion,

            ObligacionFinanciera.id_usuario
            == id_usuario
        )
        .with_for_update()
    )

    return db.scalar(consulta)


def bloquear_cuenta_obligacion(
    db: Session,
    id_cuenta: int,
    id_usuario: int
):
    consulta = (
        select(CuentaFinanciera)
        .where(
            CuentaFinanciera.id_cuenta
            == id_cuenta,

            CuentaFinanciera.id_usuario
            == id_usuario
        )
        .with_for_update()
    )

    return db.scalar(consulta)


def buscar_movimiento_obligacion_uuid(
    db: Session,
    uuid_local
):
    return db.scalar(
        select(Movimiento).where(
            Movimiento.uuid_local == uuid_local
        )
    )


def obtener_abonos_obligacion(
    db: Session,
    id_obligacion: int,
    tipo_movimiento: str
):
    consulta = (
        select(Movimiento)
        .where(
            Movimiento.id_obligacion
            == id_obligacion,

            Movimiento.origen
            == "OBLIGACION",

            Movimiento.tipo
            == tipo_movimiento,

            Movimiento.estado
            == "ACTIVO"
        )
    )

    return db.scalars(consulta).all()


def agregar_movimiento_obligacion(
    db: Session,
    movimiento: Movimiento
):
    db.add(movimiento)
    db.flush()

    return movimiento