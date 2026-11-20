
from datetime import date, timedelta
from decimal import Decimal

from app.models import MetaFinanciera

from app.tests.helpers import (
    crear_usuario_autenticado,
    crear_cuenta,
)


def datos_meta(
    nombre="Meta de prueba",
    monto="1000.00"
):
    return {
        "nombre_meta": nombre,
        "monto_objetivo": monto,
        "fecha_objetivo": (
            date.today() + timedelta(days=90)
        ).isoformat(),
        "descripcion": "Meta pytest"
    }


def crear_meta_prueba(
    client,
    headers,
    nombre="Meta de prueba",
    monto="1000.00"
):
    respuesta = client.post(
        "/metas/",
        headers=headers,
        json=datos_meta(nombre, monto)
    )

    assert respuesta.status_code == 201

    return respuesta.json()


def test_creacion_y_planificacion(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.metas.crear@example.com"
    )

    creada = crear_meta_prueba(
        client,
        headers,
        "Comprar computador",
        "2000000.00"
    )

    assert creada["id_usuario"] == usuario.id_usuario
    assert creada["estado"] == "ACTIVA"
    assert Decimal(
        str(creada["monto_acumulado"])
    ) == Decimal("0.00")

    guardada = db_session.get(
        MetaFinanciera,
        creada["id_meta"]
    )

    assert guardada is not None

    listado = client.get(
        "/metas/",
        headers=headers
    )

    assert listado.status_code == 200
    assert any(
        m["id_meta"] == creada["id_meta"]
        for m in listado.json()
    )

    plan = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    assert plan.status_code == 200

    meta = next(
        m for m in plan.json()["metas"]
        if m["id_meta"] == creada["id_meta"]
    )

    assert Decimal(
        str(meta["porcentaje_progreso"])
    ) == Decimal("0.00")


def test_aporte_reintento_y_cumplimiento(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.metas.aportes@example.com"
    )

    creada = crear_meta_prueba(
        client,
        headers,
        "Viaje de vacaciones"
    )

    ruta = f"/metas/{creada['id_meta']}/aportes"

    primer_aporte = {
        "monto": "400.00",
        "acumulado_esperado": "0.00"
    }

    primera = client.post(
        ruta,
        headers=headers,
        json=primer_aporte
    )

    assert primera.status_code == 200
    assert primera.json()["creado"] is True
    assert Decimal(
        str(primera.json()["monto_acumulado"])
    ) == Decimal("400.00")

    assert Decimal(
        str(primera.json()["porcentaje_progreso"])
    ) == Decimal("40.00")

    # Misma operación después de perder respuesta.
    reintento = client.post(
        ruta,
        headers=headers,
        json=primer_aporte
    )

    assert reintento.status_code == 200
    assert reintento.json()["creado"] is False

    segundo = client.post(
        ruta,
        headers=headers,
        json={
            "monto": "300.00",
            "acumulado_esperado": "400.00"
        }
    )

    assert segundo.status_code == 200

    # Un reintento demasiado antiguo no puede
    # modificar el acumulado que ya avanzó.
    antiguo = client.post(
        ruta,
        headers=headers,
        json=primer_aporte
    )

    assert antiguo.status_code == 409

    completar = client.post(
        ruta,
        headers=headers,
        json={
            "monto": "300.00",
            "acumulado_esperado": "700.00"
        }
    )

    assert completar.status_code == 200
    assert completar.json()["estado"] == "CUMPLIDA"

    detalle = client.get(
        f"/metas/{creada['id_meta']}",
        headers=headers
    )

    assert detalle.status_code == 200
    assert Decimal(
        str(detalle.json()["monto_acumulado"])
    ) == Decimal("1000.00")

    exceso = client.post(
        ruta,
        headers=headers,
        json={
            "monto": "100.00",
            "acumulado_esperado": "1000.00"
        }
    )

    assert exceso.status_code == 409


def test_no_aportar_por_encima_del_objetivo(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.metas.exceso@example.com"
    )

    creada = crear_meta_prueba(
        client,
        headers,
        "Ahorro limitado",
        "1000.00"
    )

    respuesta = client.post(
        f"/metas/{creada['id_meta']}/aportes",
        headers=headers,
        json={
            "monto": "1001.00",
            "acumulado_esperado": "0.00"
        }
    )

    assert respuesta.status_code == 409

    detalle = client.get(
        f"/metas/{creada['id_meta']}",
        headers=headers
    )

    assert Decimal(
        str(detalle.json()["monto_acumulado"])
    ) == Decimal("0.00")


def test_aporte_no_modifica_saldo_bancario(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.metas.saldo@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta ahorro QA",
        "50000.00"
    )

    creada = crear_meta_prueba(
        client,
        headers,
        "Fondo de emergencias",
        "20000.00"
    )

    aporte = client.post(
        f"/metas/{creada['id_meta']}/aportes",
        headers=headers,
        json={
            "monto": "5000.00",
            "acumulado_esperado": "0.00"
        }
    )

    assert aporte.status_code == 200

    cuentas = client.get(
        "/auth/mis-cuentas",
        headers=headers
    )

    assert cuentas.status_code == 200

    actual = next(
        c for c in cuentas.json()["cuentas"]
        if c["id_cuenta"] == cuenta.id_cuenta
    )

    assert Decimal(
        str(actual["saldo_actual"])
    ) == Decimal("50000.00")


def test_editar_y_ampliar_meta_cumplida(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.metas.editar@example.com"
    )

    creada = crear_meta_prueba(
        client,
        headers,
        "Meta inicial",
        "1000.00"
    )

    id_meta = creada["id_meta"]

    nueva_fecha = (
        date.today() + timedelta(days=120)
    ).isoformat()

    editada = client.patch(
        f"/metas/{id_meta}",
        headers=headers,
        json={
            "nombre_meta": "Meta actualizada",
            "monto_objetivo": "2000.00",
            "fecha_objetivo": nueva_fecha,
            "descripcion": "Objetivo actualizado"
        }
    )

    assert editada.status_code == 200
    assert editada.json()["nombre_meta"] == "Meta actualizada"
    assert editada.json()["fecha_objetivo"] == nueva_fecha

    aporte = client.post(
        f"/metas/{id_meta}/aportes",
        headers=headers,
        json={
            "monto": "2000.00",
            "acumulado_esperado": "0.00"
        }
    )

    assert aporte.status_code == 200
    assert aporte.json()["estado"] == "CUMPLIDA"

    ampliada = client.patch(
        f"/metas/{id_meta}",
        headers=headers,
        json={
            "monto_objetivo": "3000.00"
        }
    )

    assert ampliada.status_code == 200
    assert ampliada.json()["estado"] == "ACTIVA"

    bajar = client.patch(
        f"/metas/{id_meta}",
        headers=headers,
        json={
            "monto_objetivo": "1900.00"
        }
    )

    assert bajar.status_code == 409


def test_desactivar_solo_meta_sin_ahorro(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.metas.desactivar@example.com"
    )

    vacia = crear_meta_prueba(
        client,
        headers,
        "Meta vacía"
    )

    ruta = f"/metas/{vacia['id_meta']}/desactivar"

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
        f"/metas/{vacia['id_meta']}",
        headers=headers,
        json={
            "nombre_meta": "No permitido"
        }
    )

    assert editar.status_code == 409

    otra = crear_meta_prueba(
        client,
        headers,
        "Meta con aporte"
    )

    client.post(
        f"/metas/{otra['id_meta']}/aportes",
        headers=headers,
        json={
            "monto": "200.00",
            "acumulado_esperado": "0.00"
        }
    )

    rechazada = client.post(
        f"/metas/{otra['id_meta']}/desactivar",
        headers=headers
    )

    assert rechazada.status_code == 409


def test_aislamiento_usuarios(
    client,
    db_session
):
    _, headers1 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.metas.usuario1@example.com"
    )

    _, headers2 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.metas.usuario2@example.com"
    )

    creada = crear_meta_prueba(
        client,
        headers1,
        "Meta privada"
    )

    ruta = f"/metas/{creada['id_meta']}"

    assert client.get(
        ruta,
        headers=headers2
    ).status_code == 404

    assert client.patch(
        ruta,
        headers=headers2,
        json={
            "nombre_meta": "Intento ajeno"
        }
    ).status_code == 404

    assert client.post(
        ruta + "/aportes",
        headers=headers2,
        json={
            "monto": "100.00",
            "acumulado_esperado": "0.00"
        }
    ).status_code == 404

    assert client.post(
        ruta + "/desactivar",
        headers=headers2
    ).status_code == 404


def test_duplicados_y_datos_invalidos(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.metas.validar@example.com"
    )

    primera = client.post(
        "/metas/",
        headers=headers,
        json=datos_meta("  Viaje   Japón  ")
    )

    segunda = client.post(
        "/metas/",
        headers=headers,
        json=datos_meta("viaje japón")
    )

    assert primera.status_code == 201
    assert segunda.status_code == 409

    negativo = client.post(
        "/metas/",
        headers=headers,
        json=datos_meta(
            "Meta negativa",
            "-100.00"
        )
    )

    assert negativo.status_code == 422

    futuro = datos_meta("Meta fecha pasada")
    futuro["fecha_objetivo"] = (
        date.today() - timedelta(days=1)
    ).isoformat()

    assert client.post(
        "/metas/",
        headers=headers,
        json=futuro
    ).status_code == 422

    propietario = datos_meta("Propietario indebido")
    propietario["id_usuario"] = 999999

    assert client.post(
        "/metas/",
        headers=headers,
        json=propietario
    ).status_code == 422


def test_metas_requieren_token(client):
    assert client.get(
        "/metas/"
    ).status_code == 401

    assert client.post(
        "/metas/",
        json=datos_meta()
    ).status_code == 401

    assert client.post(
        "/metas/1/aportes",
        json={
            "monto": "100.00",
            "acumulado_esperado": "0.00"
        }
    ).status_code == 401
