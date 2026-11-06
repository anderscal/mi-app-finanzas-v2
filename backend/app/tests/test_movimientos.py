from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from app.models import Movimiento

from app.tests.helpers import (
    crear_cuenta,
    crear_usuario_autenticado,
    obtener_categoria_sistema,
)


def test_movimiento_normal_idempotente(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "pytest.movimiento@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta movimiento pytest",
        "100000.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    uuid_local = (
        "914ca72c-6824-4b27-"
        "9264-000000000001"
    )

    datos = {
        "uuid_local": uuid_local,
        "id_cuenta": cuenta.id_cuenta,
        "id_categoria": categoria.id_categoria,
        "tipo": "GASTO",
        "monto": "10000.00",
        "fecha_movimiento": "2026-11-06",
        "descripcion": "Gasto pytest"
    }

    # Primera solicitud
    respuesta_1 = client.post(
        "/movimientos/normales",
        headers=headers,
        json=datos
    )

    assert respuesta_1.status_code == 200
    assert respuesta_1.json()["creado"] is True

    id_movimiento = respuesta_1.json()[
        "id_movimiento"
    ]

    # Repetir exactamente la misma operación
    respuesta_2 = client.post(
        "/movimientos/normales",
        headers=headers,
        json=datos
    )

    assert respuesta_2.status_code == 200
    assert respuesta_2.json()["creado"] is False

    assert (
        respuesta_2.json()["id_movimiento"]
        == id_movimiento
    )

    # Debe existir una sola fila con ese UUID
    cantidad = db_session.scalar(
        select(
            func.count(
                Movimiento.id_movimiento
            )
        ).where(
            Movimiento.uuid_local
            == UUID(uuid_local)
        )
    )

    assert cantidad == 1

    # Y el saldo debe bajar una sola vez.
    cuentas = client.get(
        "/auth/mis-cuentas",
        headers=headers
    )

    assert cuentas.status_code == 200

    cuenta_json = cuentas.json()["cuentas"][0]

    assert Decimal(
        str(cuenta_json["saldo_actual"])
    ) == Decimal("90000.00")