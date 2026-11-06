
from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    CategoriaMovimiento,
    CuentaFinanciera,
    MetaFinanciera,
    Movimiento,
    ObligacionFinanciera,
    Presupuesto,
)


def obtener_presupuestos(db: Session, id_usuario: int):

    # Sumar gastos normales activos para cada
    # usuario, categoria, mes y año.
    gastado = (
        select(
            func.coalesce(
                func.sum(
                    Movimiento.monto + Movimiento.monto_gmf
                ),
                0
            )
        )
        .select_from(Movimiento)
        .join(
            CuentaFinanciera,
            Movimiento.id_cuenta == CuentaFinanciera.id_cuenta
        )
        .where(
            CuentaFinanciera.id_usuario == Presupuesto.id_usuario,
            Movimiento.id_categoria == Presupuesto.id_categoria,
            Movimiento.tipo == "GASTO",
            Movimiento.origen == "NORMAL",
            Movimiento.estado == "ACTIVO",
            extract("year", Movimiento.fecha_movimiento)
            == Presupuesto.anio,
            extract("month", Movimiento.fecha_movimiento)
            == Presupuesto.mes
        )
        .correlate(Presupuesto)
        .scalar_subquery()
    )

    consulta = (
        select(
            Presupuesto.id_presupuesto,
            Presupuesto.anio,
            Presupuesto.mes,
            Presupuesto.monto_limite,
            CategoriaMovimiento.nombre_categoria,
            gastado.label("gastado")
        )
        .join(
            CategoriaMovimiento,
            Presupuesto.id_categoria
            == CategoriaMovimiento.id_categoria
        )
        .where(Presupuesto.id_usuario == id_usuario)
        .order_by(
            Presupuesto.anio.desc(),
            Presupuesto.mes.desc(),
            Presupuesto.id_presupuesto
        )
    )

    return db.execute(consulta).mappings().all()


def obtener_metas(db: Session, id_usuario: int):

    consulta = (
        select(MetaFinanciera)
        .where(MetaFinanciera.id_usuario == id_usuario)
        .order_by(MetaFinanciera.id_meta)
    )

    return db.scalars(consulta).all()


def obtener_obligaciones(db: Session, id_usuario: int):

    # Solo pagos de obligaciones POR_PAGAR
    # o cobros de obligaciones POR_COBRAR.
    abonado = (
        select(
            func.coalesce(func.sum(Movimiento.monto), 0)
        )
        .select_from(Movimiento)
        .join(
            CuentaFinanciera,
            Movimiento.id_cuenta == CuentaFinanciera.id_cuenta
        )
        .where(
            Movimiento.id_obligacion
            == ObligacionFinanciera.id_obligacion,
            CuentaFinanciera.id_usuario
            == ObligacionFinanciera.id_usuario,
            Movimiento.origen == "OBLIGACION",
            Movimiento.estado == "ACTIVO",
            or_(
                and_(
                    ObligacionFinanciera.tipo_obligacion == "POR_PAGAR",
                    Movimiento.tipo == "GASTO"
                ),
                and_(
                    ObligacionFinanciera.tipo_obligacion == "POR_COBRAR",
                    Movimiento.tipo == "INGRESO"
                )
            )
        )
        .correlate(ObligacionFinanciera)
        .scalar_subquery()
    )

    consulta = (
        select(
            ObligacionFinanciera.id_obligacion,
            ObligacionFinanciera.nombre_obligacion,
            ObligacionFinanciera.tipo_obligacion,
            ObligacionFinanciera.monto_original,
            ObligacionFinanciera.estado,
            abonado.label("total_abonado")
        )
        .where(
            ObligacionFinanciera.id_usuario == id_usuario
        )
        .order_by(ObligacionFinanciera.id_obligacion)
    )

    return db.execute(consulta).mappings().all()
    