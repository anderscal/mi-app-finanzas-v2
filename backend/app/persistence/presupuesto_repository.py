
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CategoriaMovimiento,
    Presupuesto,
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


def obtener_categoria_presupuesto(
    db: Session,
    id_categoria: int
):
    return db.get(
        CategoriaMovimiento,
        id_categoria
    )


def obtener_presupuestos_usuario(
    db: Session,
    id_usuario: int
):
    consulta = (
        select(Presupuesto)
        .where(
            Presupuesto.id_usuario == id_usuario
        )
        .order_by(
            Presupuesto.anio.desc(),
            Presupuesto.mes.desc(),
            Presupuesto.id_presupuesto
        )
    )

    return list(
        db.scalars(consulta).all()
    )


def buscar_presupuesto_periodo(
    db: Session,
    id_usuario: int,
    id_categoria: int,
    anio: int,
    mes: int
):
    consulta = (
        select(Presupuesto)
        .where(
            Presupuesto.id_usuario == id_usuario,
            Presupuesto.id_categoria == id_categoria,
            Presupuesto.anio == anio,
            Presupuesto.mes == mes
        )
        .limit(1)
    )

    return db.scalar(consulta)


def bloquear_presupuesto_usuario(
    db: Session,
    id_usuario: int,
    id_presupuesto: int
):
    consulta = (
        select(Presupuesto)
        .where(
            Presupuesto.id_usuario == id_usuario,
            Presupuesto.id_presupuesto == id_presupuesto
        )
        .with_for_update()
    )

    return db.scalar(consulta)


def insertar_presupuesto(
    db: Session,
    presupuesto: Presupuesto
):
    db.add(presupuesto)
    db.flush()

    return presupuesto
