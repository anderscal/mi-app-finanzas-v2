from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CuentaFinanciera,
    Movimiento,
    Transferencia,
)


def buscar_movimiento_por_uuid(
    db: Session,
    uuid_local: UUID
):
    return db.scalar(
        select(Movimiento).where(
            Movimiento.uuid_local == uuid_local
        )
    )


def buscar_transferencia(
    db: Session,
    id_transferencia: int
):
    return db.get(
        Transferencia,
        id_transferencia
    )


def bloquear_cuentas_usuario(
    db: Session,
    id_usuario: int,
    id_cuenta_origen: int,
    id_cuenta_destino: int
):
    ids = sorted(
        [id_cuenta_origen, id_cuenta_destino]
    )

    consulta = (
        select(CuentaFinanciera)
        .where(
            CuentaFinanciera.id_usuario == id_usuario,
            CuentaFinanciera.id_cuenta.in_(ids)
        )
        .order_by(CuentaFinanciera.id_cuenta)
        .with_for_update()
    )

    cuentas = db.scalars(consulta).all()

    return {
        cuenta.id_cuenta: cuenta
        for cuenta in cuentas
    }


def agregar_transferencia(
    db: Session,
    transferencia: Transferencia
):
    db.add(transferencia)

    # Necesitamos obtener id_transferencia
    # antes de crear los movimientos.
    db.flush()

    return transferencia


def agregar_movimiento_transferencia(
    db: Session,
    movimiento: Movimiento
):
    db.add(movimiento)
    db.flush()

    return movimiento