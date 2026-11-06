from decimal import Decimal

from sqlalchemy import func, select

from app.models import (
    Movimiento,
    Transferencia,
)

from app.tests.helpers import (
    crear_cuenta,
    crear_usuario_autenticado,
)


def test_transferencia_atomica_e_idempotente(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "pytest.transferencia@example.com"
    )

    origen = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Origen pytest",
        "500000.00"
    )

    destino = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Destino pytest",
        "100000.00"
    )

    datos = {
        "uuid_operacion":
            "63bb2857-e289-4c47-"
            "8787-000000000001",

        "id_cuenta_origen":
            origen.id_cuenta,

        "id_cuenta_destino":
            destino.id_cuenta,

        "monto": "200000.00",

        "fecha_transferencia":
            "2026-11-06",

        "motivo":
            "Transferencia pytest",

        "aplica_gmf": True
    }

    # Primera ejecución
    respuesta_1 = client.post(
        "/transferencias/",
        headers=headers,
        json=datos
    )

    assert respuesta_1.status_code == 200

    resultado_1 = respuesta_1.json()

    assert resultado_1["creado"] is True

    assert Decimal(
        str(resultado_1["monto_gmf"])
    ) == Decimal("800.00")

    id_transferencia = resultado_1[
        "id_transferencia"
    ]

    # Deben existir exactamente dos movimientos.
    cantidad = db_session.scalar(
        select(
            func.count(
                Movimiento.id_movimiento
            )
        ).where(
            Movimiento.id_transferencia
            == id_transferencia
        )
    )

    assert cantidad == 2

    movimientos = db_session.scalars(
        select(Movimiento)
        .where(
            Movimiento.id_transferencia
            == id_transferencia
        )
        .order_by(Movimiento.id_movimiento)
    ).all()

    salida = next(
        m for m in movimientos
        if m.tipo == "GASTO"
    )

    entrada = next(
        m for m in movimientos
        if m.tipo == "INGRESO"
    )

    assert salida.monto == Decimal("200000.00")
    assert salida.monto_gmf == Decimal("800.00")

    assert entrada.monto == Decimal("200000.00")
    assert entrada.monto_gmf == Decimal("0.00")

    # Repetir exactamente la operación
    respuesta_2 = client.post(
        "/transferencias/",
        headers=headers,
        json=datos
    )

    assert respuesta_2.status_code == 200
    assert respuesta_2.json()["creado"] is False

    assert (
        respuesta_2.json()["id_transferencia"]
        == id_transferencia
    )

    # Sigue existiendo una sola transferencia.
    cantidad_transferencias = db_session.scalar(
        select(
            func.count(
                Transferencia.id_transferencia
            )
        ).where(
            Transferencia.id_transferencia
            == id_transferencia
        )
    )

    assert cantidad_transferencias == 1

    # Y siguen siendo únicamente dos movimientos.
    cantidad_movimientos = db_session.scalar(
        select(
            func.count(
                Movimiento.id_movimiento
            )
        ).where(
            Movimiento.id_transferencia
            == id_transferencia
        )
    )

    assert cantidad_movimientos == 2

    # Comprobar saldos
    respuesta_cuentas = client.get(
        "/auth/mis-cuentas",
        headers=headers
    )

    assert respuesta_cuentas.status_code == 200

    cuentas = {
        c["nombre_cuenta"]: Decimal(
            str(c["saldo_actual"])
        )
        for c in respuesta_cuentas.json()["cuentas"]
    }

    assert cuentas["Origen pytest"] == Decimal(
        "299200.00"
    )

    assert cuentas["Destino pytest"] == Decimal(
        "300000.00"
    )

    assert Decimal(
        str(
            respuesta_cuentas.json()[
                "saldo_general"
            ]
        )
    ) == Decimal("599200.00")