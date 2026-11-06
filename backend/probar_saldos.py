
from decimal import Decimal
from sqlalchemy.orm import Session

from app.persistence.database import engine
from app.business.cuenta_service import (
    consultar_resumen_cuentas
)


with Session(engine) as db:

    resumen = consultar_resumen_cuentas(
        db=db,
        id_usuario=1
    )

    print("=== SALDOS POR CUENTA ===")

    for cuenta in resumen["cuentas"]:
        print(
            cuenta["nombre_cuenta"],
            "=>",
            cuenta["saldo_actual"]
        )

    print("\n=== SALDO GENERAL ===")
    print(resumen["saldo_general"])

    # Validaciones del escenario oficial
    esperados = {
        "Cuenta principal": Decimal("2448000.00"),
        "Efectivo": Decimal("1000000.00")
    }

    for cuenta in resumen["cuentas"]:
        nombre = cuenta["nombre_cuenta"]
        assert cuenta["saldo_actual"] == esperados[nombre], (
            f"Saldo incorrecto para {nombre}"
        )

    assert resumen["saldo_general"] == Decimal("3448000.00")

    print("\nPRUEBA SUPERADA: los saldos coinciden.")
