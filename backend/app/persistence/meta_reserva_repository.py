
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    case,
    func,
    select,
)

from sqlalchemy.orm import Session

from app.models import (
    AporteMeta,
    CuentaFinanciera,
    MetaFinanciera,
    Movimiento,
    Usuario,
)


def bloquear_usuario_reservas(
    db: Session,
    id_usuario: int
):
    return db.scalar(
        select(Usuario)
        .where(
            Usuario.id_usuario == id_usuario
        )
        .with_for_update()
    )


def bloquear_cuenta_reserva(
    db: Session,
    id_usuario: int,
    id_cuenta: int
):
    return db.scalar(
        select(CuentaFinanciera)
        .where(
            CuentaFinanciera.id_usuario == id_usuario,
            CuentaFinanciera.id_cuenta == id_cuenta
        )
        .with_for_update()
    )


def bloquear_meta_reserva(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    return db.scalar(
        select(MetaFinanciera)
        .where(
            MetaFinanciera.id_usuario == id_usuario,
            MetaFinanciera.id_meta == id_meta
        )
        .with_for_update()
    )


def obtener_meta_reserva(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    return db.scalar(
        select(MetaFinanciera)
        .where(
            MetaFinanciera.id_usuario == id_usuario,
            MetaFinanciera.id_meta == id_meta
        )
    )


def obtener_cuentas_reserva(
    db: Session,
    id_usuario: int
):
    consulta = (
        select(CuentaFinanciera)
        .where(
            CuentaFinanciera.id_usuario == id_usuario
        )
        .order_by(CuentaFinanciera.id_cuenta)
    )

    return list(
        db.scalars(consulta).all()
    )


def buscar_aporte_uuid(
    db: Session,
    uuid_operacion: UUID
):
    return db.scalar(
        select(AporteMeta)
        .where(
            AporteMeta.uuid_operacion == uuid_operacion
        )
    )


def existe_uuid_movimiento_bancario(
    db: Session,
    uuid_operacion: UUID
) -> bool:
    resultado = db.scalar(
        select(Movimiento.id_movimiento)
        .where(
            Movimiento.uuid_local == uuid_operacion
        )
        .limit(1)
    )

    return resultado is not None


def _efecto_reserva():
    return case(
        (
            AporteMeta.tipo == "RESERVA",
            AporteMeta.monto
        ),
        (
            AporteMeta.tipo == "LIBERACION",
            -AporteMeta.monto
        ),
        else_=Decimal("0.00")
    )


def reservado_por_cuenta(
    db: Session,
    id_usuario: int,
    id_cuenta: int
) -> Decimal:
    total = db.scalar(
        select(
            func.coalesce(
                func.sum(_efecto_reserva()),
                0
            )
        )
        .where(
            AporteMeta.id_usuario == id_usuario,
            AporteMeta.id_cuenta == id_cuenta,
            AporteMeta.estado == "ACTIVO"
        )
    )

    return Decimal(total or 0)


def reservado_por_meta(
    db: Session,
    id_usuario: int,
    id_meta: int
) -> Decimal:
    total = db.scalar(
        select(
            func.coalesce(
                func.sum(_efecto_reserva()),
                0
            )
        )
        .where(
            AporteMeta.id_usuario == id_usuario,
            AporteMeta.id_meta == id_meta,
            AporteMeta.estado == "ACTIVO"
        )
    )

    return Decimal(total or 0)


def listar_eventos_meta(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    consulta = (
        select(AporteMeta)
        .where(
            AporteMeta.id_usuario == id_usuario,
            AporteMeta.id_meta == id_meta
        )
        .order_by(AporteMeta.id_aporte)
    )

    return list(
        db.scalars(consulta).all()
    )


def insertar_evento_reserva(
    db: Session,
    evento: AporteMeta
):
    db.add(evento)
    db.flush()

    return evento
    