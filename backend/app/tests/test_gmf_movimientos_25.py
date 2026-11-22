
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.models import Movimiento

from app.tests.helpers import (
    crear_cuenta,
    crear_usuario_autenticado,
    obtener_categoria_sistema,
)


def enviar_movimiento(
    client,
    headers,
    cuenta,
    categoria,
    tipo,
    monto,
    aplica_gmf=None,
    uuid=None,
):
    datos = {
        "uuid_local": uuid or str(uuid4()),
        "id_cuenta": cuenta.id_cuenta,
        "id_categoria": categoria.id_categoria,
        "tipo": tipo,
        "monto": monto,
        "fecha_movimiento": date.today().isoformat(),
        "descripcion": "Prueba GMF movimiento normal",
    }

    # Verificar compatibilidad con operaciones
    # offline creadas antes de agregar el campo.
    if aplica_gmf is not None:
        datos["aplica_gmf"] = aplica_gmf

    return client.post(
        "/movimientos/normales",
        headers=headers,
        json=datos
    )


def saldo_real(
    client,
    headers,
    id_cuenta
):
    respuesta = client.get(
        "/auth/mis-cuentas",
        headers=headers
    )

    assert respuesta.status_code == 200

    cuenta = next(
        c for c in respuesta.json()["cuentas"]
        if c["id_cuenta"] == id_cuenta
    )

    return Decimal(
        str(cuenta["saldo_actual"])
    )


def test_gasto_con_gmf_descuenta_y_reintento_no_duplica(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.gmf.gasto@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "GMF débito 100400",
        "200000.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    uuid = str(uuid4())

    primera = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "GASTO",
        "100000.00",
        True,
        uuid
    )

    assert primera.status_code == 200, primera.text
    assert primera.json()["creado"] is True
    assert primera.json()["aplica_gmf"] is True

    assert Decimal(
        str(primera.json()["monto_gmf"])
    ) == Decimal("400.00")

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("99600.00")

    segunda = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "GASTO",
        "100000.00",
        True,
        uuid
    )

    assert segunda.status_code == 200
    assert segunda.json()["creado"] is False

    assert (
        segunda.json()["id_movimiento"]
        == primera.json()["id_movimiento"]
    )

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("99600.00")

    cantidad = db_session.scalar(
        select(
            func.count(
                Movimiento.id_movimiento
            )
        ).where(
            Movimiento.uuid_local == UUID(uuid)
        )
    )

    assert cantidad == 1

    # Mismo UUID con distinta selección de GMF:
    # debe rechazarse, no generar otro movimiento.
    conflicto = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "GASTO",
        "100000.00",
        False,
        uuid
    )

    assert conflicto.status_code == 409

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("99600.00")

    periodo = date.today()

    resumen = client.get(
        "/consultas/resumen-mensual",
        params={
            "anio": periodo.year,
            "mes": periodo.month
        },
        headers=headers
    )

    assert resumen.status_code == 200

    assert Decimal(
        str(resumen.json()["gmf_total"])
    ) == Decimal("400.00")


def test_gasto_antiguo_sin_campo_gmf_mantiene_compatibilidad(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.gmf.legado@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "GMF formato antiguo",
        "20000.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    # No enviamos aplica_gmf.
    r = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "GASTO",
        "10000.00"
    )

    assert r.status_code == 200, r.text

    assert r.json()["aplica_gmf"] is False

    assert Decimal(
        str(r.json()["monto_gmf"])
    ) == Decimal("0.00")

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("10000.00")


def test_ingreso_no_admite_gmf(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.gmf.ingreso@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "GMF ingresos",
        "0.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "INGRESO"
    )

    rechazada = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "INGRESO",
        "5000.00",
        True
    )

    assert rechazada.status_code == 422

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("0.00")

    aceptada = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "INGRESO",
        "5000.00",
        False
    )

    assert aceptada.status_code == 200

    assert Decimal(
        str(aceptada.json()["monto_gmf"])
    ) == Decimal("0.00")

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("5000.00")


def test_gasto_exige_saldo_para_monto_mas_gmf(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.gmf.saldo@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "GMF saldo justo",
        "1000.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    rechazada = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "GASTO",
        "1000.00",
        True
    )

    assert rechazada.status_code == 409

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("1000.00")

    permitido = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "GASTO",
        "1000.00",
        False
    )

    assert permitido.status_code == 200

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("0.00")


def test_gmf_respeta_reservas_de_metas(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.gmf.reserva@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "GMF meta protegida",
        "1000.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    meta = client.post(
        "/metas/",
        headers=headers,
        json={
            "nombre_meta": "Meta proteger GMF",
            "monto_objetivo": "1000.00",
            "fecha_objetivo": (
                date.today() + timedelta(days=30)
            ).isoformat(),
            "descripcion": "Reservas en gastos con GMF",
        }
    )

    assert meta.status_code == 201, meta.text

    reserva = client.post(
        f"/metas/{meta.json()['id_meta']}/reservas",
        headers=headers,
        json={
            "uuid_operacion": str(uuid4()),
            "id_cuenta": cuenta.id_cuenta,
            "monto": "600.00",
            "fecha_operacion": date.today().isoformat(),
        }
    )

    assert reserva.status_code == 201, reserva.text

    # Hay $400 libres.
    # $399 + $1,60 de GMF no caben.
    rechazada = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "GASTO",
        "399.00",
        True
    )

    assert rechazada.status_code == 409

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("1000.00")

    # $398 + $1,59 de GMF = $399,59:
    # el saldo libre sí alcanza.
    aceptada = enviar_movimiento(
        client,
        headers,
        cuenta,
        categoria,
        "GASTO",
        "398.00",
        True
    )

    assert aceptada.status_code == 200, aceptada.text

    assert Decimal(
        str(aceptada.json()["monto_gmf"])
    ) == Decimal("1.59")

    assert saldo_real(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("600.41")

    saldos = client.get(
        "/metas/reservas/cuentas",
        headers=headers
    )

    assert saldos.status_code == 200

    detalle = next(
        c for c in saldos.json()
        if c["id_cuenta"] == cuenta.id_cuenta
    )

    assert Decimal(
        str(detalle["monto_reservado"])
    ) == Decimal("600.00")

    assert Decimal(
        str(detalle["saldo_libre"])
    ) == Decimal("0.41")
