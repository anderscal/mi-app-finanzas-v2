from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CuentaFinanciera,
    ObligacionFinanciera,
    Usuario,
)

def preparar_usuario(
    client,
    db_session
):
    email = "pytest.obligaciones@example.com"
    password = "PasswordPrueba2026!"

    respuesta = client.post(
        "/auth/registro",
        json={
            "nombre_1": "Test",
            "nombre_2": None,
            "apellido_1": "Obligaciones",
            "apellido_2": None,
            "email": email,
            "password": password
        }
    )

    assert respuesta.status_code == 201

    usuario = db_session.scalar(
        select(Usuario).where(
            Usuario.email == email
        )
    )

    cuenta = CuentaFinanciera(
        id_usuario=usuario.id_usuario,
        nombre_cuenta="Cuenta pytest",
        tipo_cuenta="AHORROS",
        institucion="Banco test",
        saldo_inicial=Decimal("100000.00"),
        estado="ACTIVA"
    )

    obligacion = ObligacionFinanciera(
        id_usuario=usuario.id_usuario,
        nombre_obligacion="Deuda pytest",
        tipo_obligacion="POR_PAGAR",
        monto_original=Decimal("30000.00"),
        fecha_inicio=date.today(),
        fecha_vencimiento=None,
        descripcion="Prueba orden anulaciones",
        estado="ACTIVA"
    )

    db_session.add_all([
        cuenta,
        obligacion
    ])

    db_session.commit()

    login = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password
        }
    )

    assert login.status_code == 200

    token = login.json()[
        "access_token"
    ]

    headers = {
        "Authorization":
            f"Bearer {token}"
    }

    return (
        cuenta,
        obligacion,
        headers
    )
def test_anular_pagos_fuera_de_orden(
    client,
    db_session
):

    cuenta, obligacion, headers = (
        preparar_usuario(
            client,
            db_session
        )
    )

    uuids = [
        "aa8f5202-0af9-45d4-b38b-000000000001",
        "aa8f5202-0af9-45d4-b38b-000000000002",
        "aa8f5202-0af9-45d4-b38b-000000000003",
    ]

    movimientos = []

    for numero, uuid in enumerate(
        uuids,
        start=1
    ):
        respuesta = client.post(
            "/obligaciones/abonos",
            headers=headers,
            json={
                "uuid_local": uuid,

                "id_cuenta":
                    cuenta.id_cuenta,

                "id_obligacion":
                    obligacion.id_obligacion,

                "monto":
                    "10000.00",

                "fecha_movimiento":
                    str(date.today()),

                "descripcion":
                    f"Pago {numero}"
            }
        )

        assert respuesta.status_code == 200

        movimientos.append(
            respuesta.json()[
                "id_movimiento"
            ]
        )

    # Los tres pagos completaron 30.000.
    db_session.expire_all()

    obligacion_actual = db_session.get(
        ObligacionFinanciera,
        obligacion.id_obligacion
    )

    assert (
        obligacion_actual.estado
        == "SALDADA"
    )

    # ----------------------------------
    # ANULAR PAGO 2
    # ----------------------------------

    respuesta = client.post(
        (
            f"/movimientos/"
            f"{movimientos[1]}/anular"
        ),
        headers=headers
    )

    assert respuesta.status_code == 200

    db_session.expire_all()

    obligacion_actual = db_session.get(
        ObligacionFinanciera,
        obligacion.id_obligacion
    )

    assert (
        obligacion_actual.estado
        == "ACTIVA"
    )

    planificacion = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    assert planificacion.status_code == 200

    deuda = next(
        item
        for item
        in planificacion.json()[
            "obligaciones"
        ]
        if item["id_obligacion"]
        == obligacion.id_obligacion
    )

    assert Decimal(
        str(deuda["monto_pendiente"])
    ) == Decimal("10000.00")

    # ----------------------------------
    # AHORA ANULAR PAGO 1
    # ----------------------------------

    respuesta = client.post(
        (
            f"/movimientos/"
            f"{movimientos[0]}/anular"
        ),
        headers=headers
    )

    assert respuesta.status_code == 200

    db_session.expire_all()

    obligacion_actual = db_session.get(
        ObligacionFinanciera,
        obligacion.id_obligacion
    )

    assert (
        obligacion_actual.estado
        == "ACTIVA"
    )

    planificacion = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    deuda = next(
        item
        for item
        in planificacion.json()[
            "obligaciones"
        ]
        if item["id_obligacion"]
        == obligacion.id_obligacion
    )

    assert Decimal(
        str(deuda["monto_pendiente"])
    ) == Decimal("20000.00")