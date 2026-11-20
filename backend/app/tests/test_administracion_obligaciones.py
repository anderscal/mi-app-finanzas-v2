
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models import ObligacionFinanciera

from app.tests.helpers import (
    crear_usuario_autenticado,
    crear_cuenta,
)


def datos_obligacion(
    nombre="Obligación QA",
    tipo="POR_PAGAR"
):
    return {
        "nombre_obligacion": nombre,
        "tipo_obligacion": tipo,
        "monto_original": "10000.00",
        "fecha_inicio": date.today().isoformat(),
        "fecha_vencimiento": (
            date.today() + timedelta(days=30)
        ).isoformat(),
        "descripcion": "Prueba de administración"
    }


def crear_obligacion_prueba(
    client,
    headers,
    nombre,
    tipo="POR_PAGAR"
):
    respuesta = client.post(
        "/obligaciones/",
        headers=headers,
        json=datos_obligacion(nombre, tipo)
    )

    assert respuesta.status_code == 201

    return respuesta.json()


@pytest.mark.parametrize(
    "tipo",
    ["POR_PAGAR", "POR_COBRAR"]
)
def test_crear_obligaciones(
    client,
    db_session,
    tipo
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        f"qa.crear.{tipo.lower()}@example.com"
    )

    respuesta = client.post(
        "/obligaciones/",
        headers=headers,
        json=datos_obligacion(
            "Obligación creada pytest",
            tipo
        )
    )

    assert respuesta.status_code == 201

    datos = respuesta.json()

    assert datos["id_usuario"] == usuario.id_usuario
    assert datos["tipo_obligacion"] == tipo
    assert datos["estado"] == "ACTIVA"
    assert Decimal(
        str(datos["monto_original"])
    ) == Decimal("10000.00")

    guardada = db_session.get(
        ObligacionFinanciera,
        datos["id_obligacion"]
    )

    assert guardada is not None
    assert guardada.id_usuario == usuario.id_usuario

    resumen = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    assert resumen.status_code == 200

    encontrada = next(
        o for o in resumen.json()["obligaciones"]
        if o["id_obligacion"] == datos["id_obligacion"]
    )

    assert Decimal(
        str(encontrada["monto_pendiente"])
    ) == Decimal("10000.00")

    assert Decimal(
        str(encontrada["total_abonado"])
    ) == Decimal("0.00")


def test_editar_obligacion(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.editar.obligacion@example.com"
    )

    creada = crear_obligacion_prueba(
        client,
        headers,
        "Deuda original"
    )

    id_obligacion = creada["id_obligacion"]

    nuevo_vencimiento = (
        date.today() + timedelta(days=45)
    ).isoformat()

    respuesta = client.patch(
        f"/obligaciones/{id_obligacion}",
        headers=headers,
        json={
            "nombre_obligacion": "Deuda actualizada",
            "fecha_vencimiento": nuevo_vencimiento,
            "descripcion": "Nuevo detalle"
        }
    )

    assert respuesta.status_code == 200

    datos = respuesta.json()

    assert datos["nombre_obligacion"] == "Deuda actualizada"
    assert datos["descripcion"] == "Nuevo detalle"
    assert datos["fecha_vencimiento"] == nuevo_vencimiento
    assert datos["monto_original"] == creada["monto_original"]
    assert datos["tipo_obligacion"] == "POR_PAGAR"

    detalle = client.get(
        f"/obligaciones/{id_obligacion}",
        headers=headers
    )

    assert detalle.status_code == 200
    assert detalle.json()["nombre_obligacion"] == "Deuda actualizada"

    indebida = client.patch(
        f"/obligaciones/{id_obligacion}",
        headers=headers,
        json={
            "monto_original": "99999.00"
        }
    )

    assert indebida.status_code == 422


def test_no_administrar_obligacion_ajena(
    client,
    db_session
):
    _, headers1 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.dueno.obligacion@example.com"
    )

    _, headers2 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.otro.obligacion@example.com"
    )

    creada = crear_obligacion_prueba(
        client,
        headers1,
        "Deuda privada"
    )

    ruta = f"/obligaciones/{creada['id_obligacion']}"

    assert client.get(
        ruta,
        headers=headers2
    ).status_code == 404

    assert client.patch(
        ruta,
        headers=headers2,
        json={"nombre_obligacion": "Intento ajeno"}
    ).status_code == 404

    assert client.post(
        ruta + "/desactivar",
        headers=headers2
    ).status_code == 404


def test_duplicados_y_validaciones(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.validacion.obligacion@example.com"
    )

    primera = client.post(
        "/obligaciones/",
        headers=headers,
        json=datos_obligacion("Banco principal")
    )

    segunda = client.post(
        "/obligaciones/",
        headers=headers,
        json=datos_obligacion("  banco   principal ")
    )

    assert primera.status_code == 201
    assert segunda.status_code == 409

    monto_invalido = datos_obligacion(
        "Monto inválido"
    )
    monto_invalido["monto_original"] = "-100.00"

    assert client.post(
        "/obligaciones/",
        headers=headers,
        json=monto_invalido
    ).status_code == 422

    propietario_indebido = datos_obligacion(
        "Propietario indebido"
    )
    propietario_indebido["id_usuario"] = 999999

    assert client.post(
        "/obligaciones/",
        headers=headers,
        json=propietario_indebido
    ).status_code == 422

    fecha_invalida = datos_obligacion(
        "Fecha inválida"
    )
    fecha_invalida["fecha_inicio"] = (
        date.today() + timedelta(days=2)
    ).isoformat()

    assert client.post(
        "/obligaciones/",
        headers=headers,
        json=fecha_invalida
    ).status_code == 422


def test_desactivar_sin_abonos(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.desactivar.obligacion@example.com"
    )

    creada = crear_obligacion_prueba(
        client,
        headers,
        "Obligación sin abonos"
    )

    ruta = (
        f"/obligaciones/{creada['id_obligacion']}"
        "/desactivar"
    )

    primera = client.post(
        ruta,
        headers=headers
    )

    segunda = client.post(
        ruta,
        headers=headers
    )

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["estado"] == "INACTIVA"

    editar = client.patch(
        f"/obligaciones/{creada['id_obligacion']}",
        headers=headers,
        json={
            "nombre_obligacion": "Intento posterior"
        }
    )

    assert editar.status_code == 409

    plan = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    assert plan.status_code == 200

    encontrada = next(
        o for o in plan.json()["obligaciones"]
        if o["id_obligacion"] == creada["id_obligacion"]
    )

    assert encontrada["estado"] == "INACTIVA"


def test_no_desactivar_con_abonos(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.abonos.obligacion@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta de abonos QA",
        "50000.00"
    )

    creada = crear_obligacion_prueba(
        client,
        headers,
        "Deuda con pago"
    )

    abono = client.post(
        "/obligaciones/abonos",
        headers=headers,
        json={
            "uuid_local": str(uuid4()),
            "id_cuenta": cuenta.id_cuenta,
            "id_obligacion": creada["id_obligacion"],
            "monto": "1000.00",
            "fecha_movimiento": date.today().isoformat(),
            "descripcion": "Pago de prueba"
        }
    )

    assert abono.status_code == 200

    desactivar = client.post(
        f"/obligaciones/{creada['id_obligacion']}/desactivar",
        headers=headers
    )

    assert desactivar.status_code == 409

    db_session.expire_all()

    obligacion = db_session.get(
        ObligacionFinanciera,
        creada["id_obligacion"]
    )

    assert obligacion.estado == "ACTIVA"


def test_requiere_autenticacion(client):
    assert client.post(
        "/obligaciones/",
        json=datos_obligacion()
    ).status_code == 401

    assert client.get(
        "/obligaciones/1"
    ).status_code == 401

    assert client.patch(
        "/obligaciones/1",
        json={"nombre_obligacion": "No permitido"}
    ).status_code == 401

    assert client.post(
        "/obligaciones/1/desactivar"
    ).status_code == 401
