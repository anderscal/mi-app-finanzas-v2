"""Lecturas PostgreSQL para la proyeccion RDF.

Capa Persistence.

No publica grafos.
No ejecuta movimientos financieros.
No confirma transacciones.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    CategoriaMovimiento,
    CuentaFinanciera,
    MetaFinanciera,
    Movimiento,
    ObligacionFinanciera,
    Presupuesto,
    Transferencia,
)

from app.models.aporte_meta import AporteMeta


def obtener_cuentas(
    db: Session,
    id_usuario: int,
):

    consulta = (
        select(CuentaFinanciera)
        .where(
            CuentaFinanciera.id_usuario == id_usuario
        )
        .order_by(CuentaFinanciera.id_cuenta)
    )

    return list(db.scalars(consulta))


def obtener_metas(
    db: Session,
    id_usuario: int,
):

    consulta = (
        select(MetaFinanciera)
        .where(
            MetaFinanciera.id_usuario == id_usuario
        )
        .order_by(MetaFinanciera.id_meta)
    )

    return list(db.scalars(consulta))


def obtener_obligaciones(
    db: Session,
    id_usuario: int,
):

    consulta = (
        select(ObligacionFinanciera)
        .where(
            ObligacionFinanciera.id_usuario == id_usuario
        )
        .order_by(
            ObligacionFinanciera.id_obligacion
        )
    )

    return list(db.scalars(consulta))


def obtener_aportes(
    db: Session,
    id_usuario: int,
):

    consulta = (
        select(AporteMeta)
        .where(
            AporteMeta.id_usuario == id_usuario
        )
        .order_by(AporteMeta.id_aporte)
    )

    return list(db.scalars(consulta))


def obtener_categorias(
    db: Session,
    id_usuario: int,
):

    consulta = (
        select(CategoriaMovimiento)
        .where(
            or_(
                CategoriaMovimiento.id_usuario
                == id_usuario,

                CategoriaMovimiento.es_sistema.is_(
                    True
                ),
            )
        )
        .order_by(
            CategoriaMovimiento.id_categoria
        )
    )

    return list(db.scalars(consulta))


def obtener_movimientos(
    db: Session,
    id_usuario: int,
):

    consulta = (
        select(Movimiento)
        .join(
            CuentaFinanciera,

            Movimiento.id_cuenta
            == CuentaFinanciera.id_cuenta,
        )
        .where(
            CuentaFinanciera.id_usuario == id_usuario
        )
        .order_by(Movimiento.id_movimiento)
    )

    return list(db.scalars(consulta))


def obtener_transferencias(
    db: Session,
    id_usuario: int,
):

    consulta = (
        select(Transferencia)
        .join(
            CuentaFinanciera,

            Transferencia.id_cuenta_origen
            == CuentaFinanciera.id_cuenta,
        )
        .where(
            CuentaFinanciera.id_usuario == id_usuario
        )
        .order_by(
            Transferencia.id_transferencia
        )
    )

    return list(db.scalars(consulta))


def obtener_presupuestos(
    db: Session,
    id_usuario: int,
):

    consulta = (
        select(Presupuesto)
        .where(
            Presupuesto.id_usuario == id_usuario
        )
        .order_by(
            Presupuesto.id_presupuesto
        )
    )

    return list(db.scalars(consulta))