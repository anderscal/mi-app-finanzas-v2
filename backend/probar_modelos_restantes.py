
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.database import engine
from app.models import (
    CategoriaMovimiento,
    MetaFinanciera,
    Presupuesto,
    ObligacionFinanciera,
    Transferencia,
    Movimiento
)


with Session(engine) as session:

    print("=== CATEGORÍAS ===")
    categorias = session.scalars(
        select(CategoriaMovimiento)
    ).all()

    for categoria in categorias:
        print(
            categoria.nombre_categoria,
            categoria.tipo_categoria
        )

    print("\n=== METAS ===")
    metas = session.scalars(
        select(MetaFinanciera)
    ).all()

    for meta in metas:
        print(meta.nombre_meta, meta.monto_objetivo)

    print("\n=== PRESUPUESTOS ===")
    presupuestos = session.scalars(
        select(Presupuesto)
    ).all()

    for presupuesto in presupuestos:
        print(
            presupuesto.id_presupuesto,
            presupuesto.monto_limite
        )

    print("\n=== OBLIGACIONES ===")
    obligaciones = session.scalars(
        select(ObligacionFinanciera)
    ).all()

    for obligacion in obligaciones:
        print(
            obligacion.nombre_obligacion,
            obligacion.tipo_obligacion
        )

    print("\n=== TRANSFERENCIAS ===")
    transferencias = session.scalars(
        select(Transferencia)
    ).all()

    for transferencia in transferencias:
        print(
            transferencia.id_transferencia,
            transferencia.monto
        )

    print("\n=== MOVIMIENTOS ===")
    movimientos = session.scalars(
        select(Movimiento)
        .order_by(Movimiento.id_movimiento)
    ).all()

    for movimiento in movimientos:
        print(
            movimiento.id_movimiento,
            movimiento.tipo,
            movimiento.origen,
            movimiento.monto
        )

    print("\nTotal movimientos:", len(movimientos))
