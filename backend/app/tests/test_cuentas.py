
from decimal import Decimal

from app.models import CuentaFinanciera
from app.tests.helpers import crear_usuario_autenticado


def datos_cuenta(nombre="Cuenta pytest"):
    return {
        "nombre_cuenta": nombre,
        "tipo_cuenta": "AHORROS",
        "institucion": "Banco pytest",
        "saldo_inicial": "50000.00"
    }


def test_crear_cuenta_autenticada(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "pytest.crear.cuenta@example.com"
    )

    respuesta = client.post(
        "/cuentas/",
        headers=headers,
        json=datos_cuenta()
    )

    assert respuesta.status_code == 201

    cuerpo = respuesta.json()

    assert cuerpo["id_usuario"] == usuario.id_usuario
    assert cuerpo["estado"] == "ACTIVA"
    assert cuerpo["nombre_cuenta"] == "Cuenta pytest"

    cuenta = db_session.get(
        CuentaFinanciera,
        cuerpo["id_cuenta"]
    )

    assert cuenta is not None
    assert cuenta.id_usuario == usuario.id_usuario
    assert cuenta.saldo_inicial == Decimal("50000.00")

    consulta = client.get(
        "/auth/mis-cuentas",
        headers=headers
    )

    assert consulta.status_code == 200

    ids = [
        c["id_cuenta"]
        for c in consulta.json()["cuentas"]
    ]

    assert cuerpo["id_cuenta"] in ids


def test_crear_cuenta_sin_token(client):
    respuesta = client.post(
        "/cuentas/",
        json=datos_cuenta()
    )

    assert respuesta.status_code == 401


def test_nombre_duplicado(client, db_session):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "pytest.duplicado.cuenta@example.com"
    )

    primera = client.post(
        "/cuentas/",
        headers=headers,
        json=datos_cuenta("Banco principal")
    )

    segunda = client.post(
        "/cuentas/",
        headers=headers,
        json=datos_cuenta("banco principal")
    )

    assert primera.status_code == 201
    assert segunda.status_code == 409


def test_rechazar_saldo_negativo(client, db_session):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "pytest.saldo.cuenta@example.com"
    )

    datos = datos_cuenta()
    datos["saldo_inicial"] = "-100.00"

    respuesta = client.post(
        "/cuentas/",
        headers=headers,
        json=datos
    )

    assert respuesta.status_code == 422


def test_no_permitir_asignar_otro_usuario(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "pytest.propietario.cuenta@example.com"
    )

    datos = datos_cuenta()
    datos["id_usuario"] = usuario.id_usuario + 1

    respuesta = client.post(
        "/cuentas/",
        headers=headers,
        json=datos
    )

    assert respuesta.status_code == 422
