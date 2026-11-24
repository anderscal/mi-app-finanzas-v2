
"""Lecturas SQL del RAG financiero.

Capa Persistence.
Solo datos del usuario autenticado.
No modifica registros y no realiza commits.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CuentaFinanciera,
    MetaFinanciera,
)
from app.models.aporte_meta import AporteMeta


def obtener_aportes_vinculados(
    db: Session,
    id_usuario: int,
) -> list[dict]:
    """Recupera aportes activos con sus relaciones meta-cuenta.

    Las tres entidades deben pertenecer al mismo usuario.
    No trunca filas ni modifica la base de datos.
    """

    if type(id_usuario) is not int or id_usuario <= 0:
        raise ValueError("ID de usuario inválido")

    consulta = (
        select(
            AporteMeta.id_meta.label("id_meta"),
            AporteMeta.id_cuenta.label("id_cuenta"),
            AporteMeta.tipo.label("tipo"),
            AporteMeta.monto.label("monto"),
            MetaFinanciera.nombre_meta.label("nombre_meta"),
            CuentaFinanciera.nombre_cuenta.label("nombre_cuenta"),
        )
        .join(
            MetaFinanciera,
            MetaFinanciera.id_meta == AporteMeta.id_meta,
        )
        .join(
            CuentaFinanciera,
            CuentaFinanciera.id_cuenta == AporteMeta.id_cuenta,
        )
        .where(
            AporteMeta.id_usuario == id_usuario,
            MetaFinanciera.id_usuario == id_usuario,
            CuentaFinanciera.id_usuario == id_usuario,
            AporteMeta.estado == "ACTIVO",
        )
        .order_by(
            AporteMeta.id_meta,
            AporteMeta.id_cuenta,
            AporteMeta.id_aporte,
        )
    )

    return list(
        db.execute(consulta).mappings().all()
    )
