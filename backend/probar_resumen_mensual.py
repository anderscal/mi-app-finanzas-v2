
from decimal import Decimal

from sqlalchemy.orm import Session

from app.persistence.database import engine
from app.business.movimiento_service import (
    consultar_resumen_mensual,
    consultar_historial_mensual
)


with Session(engine) as db:

    resumen = consultar_resumen_mensual(
        db=db,
        id_usuario=1,
        anio=2026,
        mes=11
    )

    print("=== RESUMEN NOVIEMBRE 2026 ===")

    for clave, valor in resumen.items():
        print(clave, ":", valor)

    assert resumen["ingresos_ordinarios"] == Decimal("3000000.00")
    assert resumen["gastos_ordinarios"] == Decimal("200000.00")
    assert resumen["balance_ordinario"] == Decimal("2800000.00")
    assert resumen["gmf_total"] == Decimal("2000.00")

    historial = consultar_historial_mensual(
        db=db,
        id_usuario=1,
        anio=2026,
        mes=11
    )

    print("\n=== HISTORIAL ===")

    for m in historial["movimientos"]:
        print(
            m["id_movimiento"],
            m["tipo"],
            m["origen"],
            m["monto"],
            m["estado"]
        )

    assert historial["total_movimientos"] == 10

    print("\nPRUEBAS SUPERADAS")
