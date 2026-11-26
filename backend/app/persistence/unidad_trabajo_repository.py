"""Operaciones ORM de la unidad de trabajo.

Capa Persistence.

Business conserva la coordinacion de las transacciones.
"""

from sqlalchemy.orm import Session


def refrescar_entidad(
    db: Session,
    entidad,
):
    """Recarga una entidad desde PostgreSQL.

    No confirma ni revierte la transaccion.
    """

    db.refresh(entidad)