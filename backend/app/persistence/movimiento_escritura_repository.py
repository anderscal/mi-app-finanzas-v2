
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import (
    CategoriaMovimiento,
    CuentaFinanciera,
    Movimiento,
)


def buscar_movimiento_uuid(db: Session, uuid_local: UUID):
    return db.scalar(
        select(Movimiento).where(
            Movimiento.uuid_local == uuid_local
        )
    )


def bloquear_cuenta(
    db: Session,
    id_cuenta: int,
    id_usuario: int
):
    consulta = (
        select(CuentaFinanciera)
        .where(
            CuentaFinanciera.id_cuenta == id_cuenta,
            CuentaFinanciera.id_usuario == id_usuario
        )
        .with_for_update()
    )
    return db.scalar(consulta)


def buscar_categoria(db: Session, id_categoria: int):
    return db.get(CategoriaMovimiento, id_categoria)


def calcular_saldo_cuenta(
    db: Session,
    cuenta: CuentaFinanciera
) -> Decimal:

    efecto = case(
        (
            Movimiento.tipo == "INGRESO",
            Movimiento.monto
        ),
        (
            Movimiento.tipo == "GASTO",
            -Movimiento.monto - Movimiento.monto_gmf
        ),
        else_=0
    )

    variacion = db.scalar(
        select(
            func.coalesce(func.sum(efecto), 0)
        ).where(
            Movimiento.id_cuenta == cuenta.id_cuenta,
            Movimiento.estado == "ACTIVO"
        )
    )

    return cuenta.saldo_inicial + variacion


def agregar_movimiento(
    db: Session,
    movimiento: Movimiento
):
    db.add(movimiento)
    db.flush()
    return movimiento
