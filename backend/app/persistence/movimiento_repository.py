
from datetime import date

from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.models import (
    Movimiento,
    CuentaFinanciera,
    CategoriaMovimiento
)


def obtener_movimientos_mes(
    db: Session,
    id_usuario: int,
    fecha_inicio: date,
    fecha_fin: date
):
    consulta = (
        select(
            Movimiento.id_movimiento,
            Movimiento.fecha_movimiento,
            Movimiento.tipo,
            Movimiento.origen,
            Movimiento.monto,
            Movimiento.monto_gmf,
            Movimiento.estado,
            Movimiento.descripcion,
            CuentaFinanciera.nombre_cuenta,
            CategoriaMovimiento.nombre_categoria
        )
        .join(
            CuentaFinanciera,
            Movimiento.id_cuenta
            == CuentaFinanciera.id_cuenta
        )
        .outerjoin(
            CategoriaMovimiento,
            Movimiento.id_categoria
            == CategoriaMovimiento.id_categoria
        )
        .where(
            CuentaFinanciera.id_usuario == id_usuario,
            Movimiento.fecha_movimiento >= fecha_inicio,
            Movimiento.fecha_movimiento < fecha_fin
        )
        .order_by(
            Movimiento.fecha_movimiento.desc(),
            Movimiento.id_movimiento.desc()
        )
    )

    return db.execute(consulta).mappings().all()


def obtener_totales_mes(
    db: Session,
    id_usuario: int,
    fecha_inicio: date,
    fecha_fin: date
):
    ingreso_normal = case(
        (
            (Movimiento.tipo == "INGRESO")
            & (Movimiento.origen == "NORMAL"),
            Movimiento.monto
        ),
        else_=0
    )

    gasto_normal = case(
        (
            (Movimiento.tipo == "GASTO")
            & (Movimiento.origen == "NORMAL"),
            Movimiento.monto
        ),
        else_=0
    )

    consulta = (
        select(
            func.coalesce(
                func.sum(ingreso_normal), 0
            ).label("ingresos"),

            func.coalesce(
                func.sum(gasto_normal), 0
            ).label("gastos"),

            func.coalesce(
                func.sum(Movimiento.monto_gmf), 0
            ).label("gmf")
        )
        .join(
            CuentaFinanciera,
            Movimiento.id_cuenta
            == CuentaFinanciera.id_cuenta
        )
        .where(
            CuentaFinanciera.id_usuario == id_usuario,
            Movimiento.estado == "ACTIVO",
            Movimiento.fecha_movimiento >= fecha_inicio,
            Movimiento.fecha_movimiento < fecha_fin
        )
    )

    return db.execute(consulta).mappings().one()
