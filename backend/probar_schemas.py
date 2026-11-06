
from pydantic import ValidationError

from app.schemas.movimiento_schema import (
    MovimientoNormalCrear
)


datos_validos = {
    "uuid_local": "550e8400-e29b-41d4-a716-446655440000",
    "id_cuenta": 1,
    "id_categoria": 1,
    "tipo": "GASTO",
    "monto": "50000.00",
    "fecha_movimiento": "2026-11-03",
    "descripcion": "Almuerzo"
}


def probar(nombre, datos, debe_ser_valido):
    try:
        movimiento = MovimientoNormalCrear(
            **datos
        )

        if not debe_ser_valido:
            raise AssertionError(
                f"{nombre}: debió ser rechazado"
            )

        print(f"OK: {nombre}")
        print(
            "Monto validado:",
            movimiento.monto
        )

    except ValidationError as error:
        if debe_ser_valido:
            raise AssertionError(
                f"{nombre}: debió ser válido"
            ) from error

        print(f"RECHAZADO CORRECTAMENTE: {nombre}")

        for problema in error.errors():
            print(
                "Campo:",
                problema["loc"],
                "| Motivo:",
                problema["msg"]
            )


# Caso 1: válido
probar(
    "Movimiento válido",
    datos_validos,
    True
)

# Caso 2: monto negativo
probar(
    "Monto negativo",
    {**datos_validos, "monto": "-50000.00"},
    False
)

# Caso 3: tipo no permitido
probar(
    "Tipo incorrecto",
    {**datos_validos, "tipo": "TRANSFERENCIA"},
    False
)

# Caso 4: campo extra
probar(
    "Estado enviado por cliente",
    {**datos_validos, "estado": "ANULADO"},
    False
)

print("\nPRUEBAS DE VALIDACIÓN SUPERADAS")
