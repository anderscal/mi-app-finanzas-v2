from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CuentaFinanciera,
    Movimiento,
    Transferencia,
    ObligacionFinanciera,
)


def bloquear_movimiento_usuario(
    db: Session,
    id_movimiento: int,
    id_usuario: int
):
    consulta = (
        select(Movimiento)
        .join(
            CuentaFinanciera,
            Movimiento.id_cuenta
            == CuentaFinanciera.id_cuenta
        )
        .where(
            Movimiento.id_movimiento
            == id_movimiento,

            CuentaFinanciera.id_usuario
            == id_usuario
        )
        .with_for_update()
    )

    return db.scalar(consulta)


def bloquear_movimientos_transferencia(
    db: Session,
    id_transferencia: int
):
    consulta = (
        select(Movimiento)
        .where(
            Movimiento.id_transferencia
            == id_transferencia
        )
        .order_by(Movimiento.id_movimiento)
        .with_for_update()
    )

    return db.scalars(consulta).all()


def bloquear_transferencia(
    db: Session,
    id_transferencia: int
):
    consulta = (
        select(Transferencia)
        .where(
            Transferencia.id_transferencia
            == id_transferencia
        )
        .with_for_update()
    )

    return db.scalar(consulta)


def bloquear_obligacion_anulacion(
    db: Session,
    id_obligacion: int
):
    consulta = (
        select(ObligacionFinanciera)
        .where(
            ObligacionFinanciera.id_obligacion
            == id_obligacion
        )
        .with_for_update()
    )

    return db.scalar(consulta)