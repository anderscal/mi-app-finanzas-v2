
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from app.models import AporteMeta

from app.tests.helpers import (
    crear_usuario_autenticado,
    crear_cuenta,
)


def datos_meta(nombre, objetivo="1000.00"):
    return {
        "nombre_meta": nombre,
        "monto_objetivo": objetivo,
        "fecha_objetivo": (
            date.today() + timedelta(days=90)
        ).isoformat(),
        "descripcion": "Meta QA de reservas"
    }


def crear_meta_qa(
    client,
    headers,
    nombre,
    objetivo="1000.00"
):
    respuesta = client.post(
        "/metas/",
        headers=headers,
        json=datos_meta(nombre, objetivo)
    )

    assert respuesta.status_code == 201
    return respuesta.json()


def operacion(id_cuenta, monto, uuid=None):
    return {
        "uuid_operacion": uuid or str(uuid4()),
        "id_cuenta": id_cuenta,
        "monto": monto,
        "fecha_operacion": date.today().isoformat()
    }


def decimal(valor):
    return Decimal(str(valor))


def buscar_saldo(client, headers, id_cuenta):
    respuesta = client.get(
        "/metas/reservas/cuentas",
        headers=headers
    )

    assert respuesta.status_code == 200

    return next(
        item
        for item in respuesta.json()
        if item["id_cuenta"] == id_cuenta
    )


def test_reservar_sin_mover_saldo_y_reintento(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.principal@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta de prueba",
        "50000.00"
    )

    meta = crear_meta_qa(
        client,
        headers,
        "Computador con reservas",
        "100000.00"
    )

    datos = operacion(
        cuenta.id_cuenta,
        "15000.00"
    )

    ruta = f"/metas/{meta['id_meta']}/reservas"

    primera = client.post(
        ruta,
        headers=headers,
        json=datos
    )

    assert primera.status_code == 201
    assert primera.json()["creado"] is True

    assert decimal(
        primera.json()["monto_acumulado"]
    ) == Decimal("15000.00")

    saldo = buscar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert decimal(
        saldo["saldo_real"]
    ) == Decimal("50000.00")

    assert decimal(
        saldo["monto_reservado"]
    ) == Decimal("15000.00")

    assert decimal(
        saldo["saldo_libre"]
    ) == Decimal("35000.00")

    # Mismo UUID y mismos datos:
    # no se duplica el ahorro.
    segunda = client.post(
        ruta,
        headers=headers,
        json=datos
    )

    assert segunda.status_code == 201
    assert segunda.json()["creado"] is False

    assert (
        primera.json()["id_aporte"]
        == segunda.json()["id_aporte"]
    )

    saldo_final = buscar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert decimal(
        saldo_final["monto_reservado"]
    ) == Decimal("15000.00")

    # El progreso sigue siendo 15 %.
    plan = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    assert plan.status_code == 200

    progreso = next(
        item
        for item in plan.json()["metas"]
        if item["id_meta"] == meta["id_meta"]
    )

    assert decimal(
        progreso["porcentaje_progreso"]
    ) == Decimal("15.00")

    eventos = (
        db_session.query(AporteMeta)
        .filter(
            AporteMeta.id_meta == meta["id_meta"]
        )
        .all()
    )

    assert len(eventos) == 1


def test_liberar_reserva_y_reintento(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.liberar@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta liberar",
        "50000.00"
    )

    meta = crear_meta_qa(
        client,
        headers,
        "Fondo para liberar",
        "30000.00"
    )

    ruta = f"/metas/{meta['id_meta']}"

    reserva = client.post(
        ruta + "/reservas",
        headers=headers,
        json=operacion(
            cuenta.id_cuenta,
            "20000.00"
        )
    )

    assert reserva.status_code == 201

    datos_liberar = operacion(
        cuenta.id_cuenta,
        "5000.00"
    )

    primera = client.post(
        ruta + "/liberaciones",
        headers=headers,
        json=datos_liberar
    )

    segunda = client.post(
        ruta + "/liberaciones",
        headers=headers,
        json=datos_liberar
    )

    assert primera.status_code == 201
    assert segunda.status_code == 201

    assert primera.json()["creado"] is True
    assert segunda.json()["creado"] is False

    saldo = buscar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert decimal(
        saldo["saldo_real"]
    ) == Decimal("50000.00")

    assert decimal(
        saldo["monto_reservado"]
    ) == Decimal("15000.00")

    assert decimal(
        saldo["saldo_libre"]
    ) == Decimal("35000.00")

    detalle = client.get(
        ruta + "/reservas",
        headers=headers
    )

    assert detalle.status_code == 200

    assert decimal(
        detalle.json()["monto_acumulado"]
    ) == Decimal("15000.00")

    assert len(detalle.json()["registros"]) == 2

    # No puede liberar más de lo reservado.
    exceso = client.post(
        ruta + "/liberaciones",
        headers=headers,
        json=operacion(
            cuenta.id_cuenta,
            "16000.00"
        )
    )

    assert exceso.status_code == 409


def test_no_reservar_dos_veces_el_saldo_libre(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.saldo@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta saldo limitado",
        "10000.00"
    )

    meta1 = crear_meta_qa(
        client,
        headers,
        "Meta primera",
        "50000.00"
    )

    meta2 = crear_meta_qa(
        client,
        headers,
        "Meta segunda",
        "50000.00"
    )

    primera = client.post(
        f"/metas/{meta1['id_meta']}/reservas",
        headers=headers,
        json=operacion(
            cuenta.id_cuenta,
            "7000.00"
        )
    )

    assert primera.status_code == 201

    # Solo quedan 3000 libres.
    segunda = client.post(
        f"/metas/{meta2['id_meta']}/reservas",
        headers=headers,
        json=operacion(
            cuenta.id_cuenta,
            "4000.00"
        )
    )

    assert segunda.status_code == 409

    saldo = buscar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert decimal(
        saldo["monto_reservado"]
    ) == Decimal("7000.00")

    assert decimal(
        saldo["saldo_libre"]
    ) == Decimal("3000.00")


def test_cumplir_meta_y_reabrir_al_liberar(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.cumplida@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta meta cumplida",
        "5000.00"
    )

    meta = crear_meta_qa(
        client,
        headers,
        "Objetivo cumplido",
        "1000.00"
    )

    ruta = f"/metas/{meta['id_meta']}"

    completa = client.post(
        ruta + "/reservas",
        headers=headers,
        json=operacion(
            cuenta.id_cuenta,
            "1000.00"
        )
    )

    assert completa.status_code == 201

    detalle = client.get(
        ruta,
        headers=headers
    )

    assert detalle.json()["estado"] == "CUMPLIDA"

    # No admite reservas adicionales.
    adicional = client.post(
        ruta + "/reservas",
        headers=headers,
        json=operacion(
            cuenta.id_cuenta,
            "100.00"
        )
    )

    assert adicional.status_code == 409

    liberacion = client.post(
        ruta + "/liberaciones",
        headers=headers,
        json=operacion(
            cuenta.id_cuenta,
            "200.00"
        )
    )

    assert liberacion.status_code == 201

    reabierta = client.get(
        ruta,
        headers=headers
    )

    assert reabierta.json()["estado"] == "ACTIVA"

    assert decimal(
        reabierta.json()["monto_acumulado"]
    ) == Decimal("800.00")


def test_varias_cuentas_y_libera_solo_su_reserva(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.multicuenta@example.com"
    )

    cuenta1 = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta reserva uno",
        "10000.00"
    )

    cuenta2 = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta reserva dos",
        "10000.00"
    )

    meta = crear_meta_qa(
        client,
        headers,
        "Meta multicuenta",
        "15000.00"
    )

    ruta = f"/metas/{meta['id_meta']}"

    for cuenta, monto in [
        (cuenta1, "2000.00"),
        (cuenta2, "3000.00"),
    ]:
        respuesta = client.post(
            ruta + "/reservas",
            headers=headers,
            json=operacion(
                cuenta.id_cuenta,
                monto
            )
        )

        assert respuesta.status_code == 201

    # No puede liberar 3000 de cuenta1,
    # porque allí solo reservó 2000.
    incorrecta = client.post(
        ruta + "/liberaciones",
        headers=headers,
        json=operacion(
            cuenta1.id_cuenta,
            "3000.00"
        )
    )

    assert incorrecta.status_code == 409

    liberar = client.post(
        ruta + "/liberaciones",
        headers=headers,
        json=operacion(
            cuenta2.id_cuenta,
            "1000.00"
        )
    )

    assert liberar.status_code == 201

    saldo1 = buscar_saldo(
        client,
        headers,
        cuenta1.id_cuenta
    )

    saldo2 = buscar_saldo(
        client,
        headers,
        cuenta2.id_cuenta
    )

    assert decimal(
        saldo1["monto_reservado"]
    ) == Decimal("2000.00")

    assert decimal(
        saldo2["monto_reservado"]
    ) == Decimal("2000.00")

    detalle = client.get(
        ruta + "/reservas",
        headers=headers
    )

    assert decimal(
        detalle.json()["monto_acumulado"]
    ) == Decimal("4000.00")


def test_aislamiento_entre_usuarios(
    client,
    db_session
):
    usuario1, headers1 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.dueno@example.com"
    )

    _, headers2 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.ajeno@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario1.id_usuario,
        "Cuenta privada reservas",
        "10000.00"
    )

    meta = crear_meta_qa(
        client,
        headers1,
        "Meta privada reservas"
    )

    ruta = f"/metas/{meta['id_meta']}"

    ajena = client.post(
        ruta + "/reservas",
        headers=headers2,
        json=operacion(
            cuenta.id_cuenta,
            "100.00"
        )
    )

    assert ajena.status_code == 404

    detalle_ajeno = client.get(
        ruta + "/reservas",
        headers=headers2
    )

    assert detalle_ajeno.status_code == 404

    saldos_ajenos = client.get(
        "/metas/reservas/cuentas",
        headers=headers2
    )

    assert saldos_ajenos.status_code == 200

    assert not any(
        item["id_cuenta"] == cuenta.id_cuenta
        for item in saldos_ajenos.json()
    )

    # El propietario tampoco puede reservar
    # utilizando una cuenta que no es suya.
    usuario2 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.tercero@example.com"
    )[0]

    cuenta_tercero = crear_cuenta(
        db_session,
        usuario2.id_usuario,
        "Cuenta tercero",
        "20000.00"
    )

    cuenta_ajena = client.post(
        ruta + "/reservas",
        headers=headers1,
        json=operacion(
            cuenta_tercero.id_cuenta,
            "100.00"
        )
    )

    assert cuenta_ajena.status_code == 404


def test_aportes_anteriores_quedan_sin_vincular(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.legado@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta legado",
        "50000.00"
    )

    meta = crear_meta_qa(
        client,
        headers,
        "Meta con ahorro anterior",
        "30000.00"
    )

    ruta = f"/metas/{meta['id_meta']}"

    # Representa un aporte anterior al paso
    # 25.1A, sin vínculo con cuenta.
    anterior = client.post(
        ruta + "/aportes",
        headers=headers,
        json={
            "monto": "10000.00",
            "acumulado_esperado": "0.00"
        }
    )

    assert anterior.status_code == 200

    detalle = client.get(
        ruta + "/reservas",
        headers=headers
    )

    assert detalle.status_code == 200

    assert decimal(
        detalle.json()["monto_sin_vincular"]
    ) == Decimal("10000.00")

    assert decimal(
        detalle.json()["monto_vinculado"]
    ) == Decimal("0.00")

    # Una reserva nueva no vuelve a
    # registrar los 10000 anteriores.
    nueva = client.post(
        ruta + "/reservas",
        headers=headers,
        json=operacion(
            cuenta.id_cuenta,
            "5000.00"
        )
    )

    assert nueva.status_code == 201

    actualizado = client.get(
        ruta + "/reservas",
        headers=headers
    )

    assert decimal(
        actualizado.json()["monto_acumulado"]
    ) == Decimal("15000.00")

    assert decimal(
        actualizado.json()["monto_vinculado"]
    ) == Decimal("5000.00")

    assert decimal(
        actualizado.json()["monto_sin_vincular"]
    ) == Decimal("10000.00")


def test_uuid_distinto_y_validaciones(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.reserva.validacion@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta validar",
        "10000.00"
    )

    meta = crear_meta_qa(
        client,
        headers,
        "Meta validar"
    )

    ruta = f"/metas/{meta['id_meta']}/reservas"

    datos = operacion(
        cuenta.id_cuenta,
        "100.00"
    )

    primera = client.post(
        ruta,
        headers=headers,
        json=datos
    )

    assert primera.status_code == 201

    # Mismo UUID, monto diferente.
    conflicto = client.post(
        ruta,
        headers=headers,
        json={
            **datos,
            "monto": "200.00"
        }
    )

    assert conflicto.status_code == 409

    # Fecha futura.
    futura = client.post(
        ruta,
        headers=headers,
        json={
            **operacion(
                cuenta.id_cuenta,
                "100.00"
            ),
            "fecha_operacion": (
                date.today() + timedelta(days=1)
            ).isoformat()
        }
    )

    assert futura.status_code == 422

    # Monto negativo.
    negativa = client.post(
        ruta,
        headers=headers,
        json=operacion(
            cuenta.id_cuenta,
            "-10.00"
        )
    )

    assert negativa.status_code == 422

    # Sin sesión.
    sin_token = client.post(
        ruta,
        json=operacion(
            cuenta.id_cuenta,
            "100.00"
        )
    )

    assert sin_token.status_code == 401

    consulta_sin_token = client.get(
        "/metas/reservas/cuentas"
    )

    assert consulta_sin_token.status_code == 401
