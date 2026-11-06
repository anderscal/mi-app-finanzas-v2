
from decimal import Decimal

from sqlalchemy.orm import Session

from app.persistence.database import engine
from app.business.planificacion_service import (
    consultar_planificacion
)


with Session(engine) as db:
    resultado = consultar_planificacion(
        db=db,
        id_usuario=1
    )

    print("=== PRESUPUESTOS ===")

    for p in resultado["presupuestos"]:
        print(
            p["categoria"],
            "Gastado:", p["gastado"],
            "Disponible:", p["disponible"],
            "Porcentaje:", p["porcentaje_usado"]
        )

    print("\n=== METAS ===")

    for m in resultado["metas"]:
        print(
            m["nombre_meta"],
            "Progreso:", m["porcentaje_progreso"]
        )

    print("\n=== OBLIGACIONES ===")

    for o in resultado["obligaciones"]:
        print(
            o["nombre_obligacion"],
            "Pendiente:", o["monto_pendiente"]
        )

    # Validaciones del escenario de prueba
    assert len(resultado["presupuestos"]) == 1
    assert len(resultado["metas"]) == 1
    assert len(resultado["obligaciones"]) == 2

    presupuesto = resultado["presupuestos"][0]
    assert presupuesto["gastado"] == Decimal("120000.00")
    assert presupuesto["disponible"] == Decimal("480000.00")
    assert presupuesto["porcentaje_usado"] == Decimal("20.00")

    meta = resultado["metas"][0]
    assert meta["porcentaje_progreso"] == Decimal("25.00")

    pendientes = {
        o["nombre_obligacion"]: o["monto_pendiente"]
        for o in resultado["obligaciones"]
    }

    assert pendientes["Crédito moto"] == Decimal("4200000.00")
    assert pendientes["Préstamo Juan"] == Decimal("350000.00")

    print("\nPRUEBAS SUPERADAS")
