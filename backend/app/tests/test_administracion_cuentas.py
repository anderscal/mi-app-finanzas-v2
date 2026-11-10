
from datetime import date
from uuid import uuid4

from app.tests.helpers import (
    crear_usuario_autenticado,
    crear_cuenta,
    obtener_categoria_sistema,
)


def test_actualizar_cuenta_propia(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "cuenta.edicion@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta original",
        "100.00"
    )

    respuesta = client.patch(
        f"/cuentas/{cuenta.id_cuenta}",
        headers=headers,
        json={
            "nombre_cuenta": "Cuenta actualizada",
            "institucion": "Banco nuevo"
        }
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["nombre_cuenta"] == "Cuenta actualizada"
    assert respuesta.json()["saldo_inicial"] == "100.00"


def test_no_modificar_cuenta_ajena(client, db_session):
    usuario1, headers1 = crear_usuario_autenticado(
        client,
        db_session,
        "propietario.cuenta@example.com"
    )

    _, headers2 = crear_usuario_autenticado(
        client,
        db_session,
        "otro.usuario.cuenta@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario1.id_usuario,
        "Cuenta privada",
        "0.00"
    )

    respuesta = client.patch(
        f"/cuentas/{cuenta.id_cuenta}",
        headers=headers2,
        json={"nombre_cuenta": "Intento ajeno"}
    )

    assert respuesta.status_code == 404

    respuesta = client.post(
        f"/cuentas/{cuenta.id_cuenta}/desactivar",
        headers=headers2
    )

    assert respuesta.status_code == 404


def test_no_modificar_saldo_inicial(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "saldo.inmutable@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta saldo",
        "100.00"
    )

    respuesta = client.patch(
        f"/cuentas/{cuenta.id_cuenta}",
        headers=headers,
        json={"saldo_inicial": "900.00"}
    )

    assert respuesta.status_code == 422


def test_no_desactivar_con_saldo(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "cuenta.con.saldo@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta con dinero",
        "100.00"
    )

    respuesta = client.post(
        f"/cuentas/{cuenta.id_cuenta}/desactivar",
        headers=headers
    )

    assert respuesta.status_code == 409

    db_session.refresh(cuenta)
    assert cuenta.estado == "ACTIVA"


def test_desactivar_saldo_cero(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "cuenta.saldo.cero@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta vacía",
        "0.00"
    )

    url = f"/cuentas/{cuenta.id_cuenta}/desactivar"

    primera = client.post(url, headers=headers)
    segunda = client.post(url, headers=headers)

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["estado"] == "INACTIVA"

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    movimiento = client.post(
        "/movimientos/normales",
        headers=headers,
        json={
            "uuid_local": str(uuid4()),
            "id_cuenta": cuenta.id_cuenta,
            "id_categoria": categoria.id_categoria,
            "tipo": "GASTO",
            "monto": "1.00",
            "fecha_movimiento": date.today().isoformat(),
            "descripcion": "Cuenta inactiva"
        }
    )

    assert movimiento.status_code == 409


def test_nombre_duplicado_al_editar(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "cuentas.duplicadas@example.com"
    )

    crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Banco principal",
        "0.00"
    )

    segunda = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Banco secundario",
        "0.00"
    )

    respuesta = client.patch(
        f"/cuentas/{segunda.id_cuenta}",
        headers=headers,
        json={"nombre_cuenta": "banco principal"}
    )

    assert respuesta.status_code == 409
