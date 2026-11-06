
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.models import CuentaFinanciera, Movimiento


def obtener_cuentas_con_saldo(
    db: Session,
    id_usuario: int
):
    # 1. Calcular el efecto de cada movimiento activo.
    efecto = case(
        (
            Movimiento.estado == "ACTIVO",
            case(
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
        ),
        else_=0
    )

    # 2. Agrupar el efecto de movimientos por cuenta.
    movimientos_por_cuenta = (
        select(
            Movimiento.id_cuenta.label("id_cuenta"),
            func.sum(efecto).label("variacion")
        )
        .group_by(Movimiento.id_cuenta)
        .subquery()
    )

    # 3. Consultar cuentas y sumar la variacion
    #    a su saldo inicial.
    consulta = (
        select(
            CuentaFinanciera.id_cuenta,
            CuentaFinanciera.nombre_cuenta,
            CuentaFinanciera.tipo_cuenta,
            CuentaFinanciera.estado,
            CuentaFinanciera.saldo_inicial,
            (
                CuentaFinanciera.saldo_inicial
                + func.coalesce(
                    movimientos_por_cuenta.c.variacion,
                    0
                )
            ).label("saldo_actual")
        )
        .outerjoin(
            movimientos_por_cuenta,
            CuentaFinanciera.id_cuenta
            == movimientos_por_cuenta.c.id_cuenta
        )
        .where(
            CuentaFinanciera.id_usuario == id_usuario
        )
        .order_by(CuentaFinanciera.id_cuenta)
    )

    return db.execute(consulta).mappings().all()
