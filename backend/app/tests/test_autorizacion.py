from app.tests.helpers import (
    crear_cuenta,
    crear_usuario_autenticado,
    obtener_categoria_sistema,
)


def test_usuario_no_puede_operar_datos_ajenos(
    client,
    db_session
):
    # Usuario A
    usuario_a, headers_a = (
        crear_usuario_autenticado(
            client,
            db_session,
            "pytest.usuario.a@example.com"
        )
    )

    cuenta_a = crear_cuenta(
        db_session,
        usuario_a.id_usuario,
        "Cuenta usuario A",
        "100000.00"
    )

    # Usuario B
    usuario_b, headers_b = (
        crear_usuario_autenticado(
            client,
            db_session,
            "pytest.usuario.b@example.com"
        )
    )

    cuenta_b = crear_cuenta(
        db_session,
        usuario_b.id_usuario,
        "Cuenta usuario B",
        "100000.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    # -----------------------------------
    # A crea un movimiento legítimo
    # -----------------------------------

    respuesta_a = client.post(
        "/movimientos/normales",
        headers=headers_a,
        json={
            "uuid_local":
                "984dcf55-f752-4859-"
                "9e72-000000000001",

            "id_cuenta":
                cuenta_a.id_cuenta,

            "id_categoria":
                categoria.id_categoria,

            "tipo":
                "GASTO",

            "monto":
                "10000.00",

            "fecha_movimiento":
                "2026-11-06",

            "descripcion":
                "Movimiento usuario A"
        }
    )

    assert respuesta_a.status_code == 200

    id_movimiento_a = respuesta_a.json()[
        "id_movimiento"
    ]

    # -----------------------------------
    # B intenta gastar desde cuenta A
    # -----------------------------------

    intento_cuenta_ajena = client.post(
        "/movimientos/normales",
        headers=headers_b,
        json={
            "uuid_local":
                "984dcf55-f752-4859-"
                "9e72-000000000002",

            "id_cuenta":
                cuenta_a.id_cuenta,

            "id_categoria":
                categoria.id_categoria,

            "tipo":
                "GASTO",

            "monto":
                "5000.00",

            "fecha_movimiento":
                "2026-11-06",

            "descripcion":
                "Intento cuenta ajena"
        }
    )

    assert intento_cuenta_ajena.status_code == 404

    # -----------------------------------
    # B intenta anular movimiento de A
    # -----------------------------------

    intento_anulacion = client.post(
        f"/movimientos/{id_movimiento_a}/anular",
        headers=headers_b
    )

    assert intento_anulacion.status_code == 404

    # -----------------------------------
    # B intenta transferir dinero
    # hacia una cuenta de A
    # -----------------------------------

    intento_transferencia = client.post(
        "/transferencias/",
        headers=headers_b,
        json={
            "uuid_operacion":
                "72527812-debc-4454-"
                "a17c-000000000001",

            "id_cuenta_origen":
                cuenta_b.id_cuenta,

            "id_cuenta_destino":
                cuenta_a.id_cuenta,

            "monto":
                "10000.00",

            "fecha_transferencia":
                "2026-11-06",

            "motivo":
                "Intento entre usuarios",

            "aplica_gmf":
                False
        }
    )

    assert intento_transferencia.status_code == 404

    # -----------------------------------
    # B únicamente debe ver su cuenta
    # -----------------------------------

    cuentas_b = client.get(
        "/auth/mis-cuentas",
        headers=headers_b
    )

    assert cuentas_b.status_code == 200

    nombres = {
        cuenta["nombre_cuenta"]
        for cuenta in cuentas_b.json()["cuentas"]
    }

    assert "Cuenta usuario B" in nombres
    assert "Cuenta usuario A" not in nombres