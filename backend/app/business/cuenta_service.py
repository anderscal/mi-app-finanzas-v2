
from decimal import Decimal
from sqlalchemy.orm import Session

from app.persistence.cuenta_repository import (
    obtener_cuentas_con_saldo
)


def consultar_resumen_cuentas(
    db: Session,
    id_usuario: int
):
    if id_usuario <= 0:
        raise ValueError("El identificador debe ser positivo")

    registros = obtener_cuentas_con_saldo(
        db=db,
        id_usuario=id_usuario
    )

    cuentas = [dict(registro) for registro in registros]

    # El saldo general incluye todas las cuentas
    # del usuario, incluso si estan inactivas.
    saldo_general = sum(
        (cuenta["saldo_actual"] for cuenta in cuentas),
        Decimal("0.00")
    )

    return {
        "id_usuario": id_usuario,
        "total_cuentas": len(cuentas),
        "saldo_general": saldo_general,
        "cuentas": cuentas
    }
