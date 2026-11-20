
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models import Movimiento

from app.tests.helpers import (
    crear_usuario_autenticado,
    crear_cuenta,
)


def datos_creacion(
    nombre: str,
    tipo: str,
    id_cuenta: int,
    uuid: str,
    gmf: bool = False
):
    return {
        "nombre_obligacion": nombre,
        "tipo_obligacion": tipo,
        "monto_original": "10000.00",
        "fecha_inicio": date.today().isoformat(),
        "fecha_vencimiento": None,
        "descripcion": "QA capital inicial",
        "registrar_movimiento_inicial": True,
        "id_cuenta_inicial": id_cuenta,
        "uuid_local_inicial": uuid,
        "aplica_gmf_inicial": gmf
    }


def saldo_cuenta(client, headers, id_cuenta):
    respuesta = client.get(
        "/auth/mis-cuentas",
        headers=headers
    )

    assert respuesta.status_code == 200

    cuenta = next(
        c for c in respuesta.json()["cuentas"]
        if c["id_cuenta"] == id_cuenta
    )

    return Decimal(str(cuenta["saldo_actual"]))


@pytest.mark.parametrize(
    "tipo,saldo_esperado,tipo_movimiento",
    [
        ("POR_COBRAR", "40000.00", "GASTO"),
        ("POR_PAGAR", "60000.00", "INGRESO"),
    ]
)
def test_movimiento_inicial_y_reintento(
    client,
    db_session,
    tipo,
    saldo_esperado,
    tipo_movimiento
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        f"qa.inicial.{tipo.lower()}@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta capital inicial",
        "50000.00"
    )

    uuid = str(uuid4())

    datos = datos_creacion(
        nombre=f"Obligación {tipo}",
        tipo=tipo,
        id_cuenta=cuenta.id_cuenta,
        uuid=uuid
    )

    primera = client.post(
        "/obligaciones/",
        headers=headers,
        json=datos
    )

    assert primera.status_code == 201

    id_obligacion = primera.json()["id_obligacion"]

    assert saldo_cuenta(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal(saldo_esperado)

    plan = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    assert plan.status_code == 200

    obligacion = next(
        o for o in plan.json()["obligaciones"]
        if o["id_obligacion"] == id_obligacion
    )

    assert Decimal(
        str(obligacion["monto_pendiente"])
    ) == Decimal("10000.00")

    assert Decimal(
        str(obligacion["total_abonado"])
    ) == Decimal("0.00")

    # Reenviar exactamente el mismo UUID
    # no debe crear otra obligación ni mover dinero.
    segunda = client.post(
        "/obligaciones/",
        headers=headers,
        json=datos
    )

    assert segunda.status_code == 201

    assert (
        segunda.json()["id_obligacion"]
        == id_obligacion
    )

    assert saldo_cuenta(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal(saldo_esperado)

    db_session.expire_all()

    movimientos = (
        db_session.query(Movimiento)
        .filter(
            Movimiento.id_obligacion == id_obligacion
        )
        .all()
    )

    assert len(movimientos) == 1
    assert movimientos[0].tipo == tipo_movimiento
    assert movimientos[0].origen == "OBLIGACION"
    assert movimientos[0].estado == "ACTIVO"

    # No puede anularse el capital inicial
    # dejando la obligación registrada.
    anulacion = client.post(
        f"/movimientos/{movimientos[0].id_movimiento}/anular",
        headers=headers
    )

    assert anulacion.status_code == 409

    # Mismo UUID con datos diferentes: conflicto.
    otros_datos = {
        **datos,
        "monto_original": "9000.00"
    }

    conflicto = client.post(
        "/obligaciones/",
        headers=headers,
        json=otros_datos
    )

    assert conflicto.status_code == 409


def test_obligacion_sin_movimiento_inicial(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.sin.inicial@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta sin movimiento",
        "50000.00"
    )

    respuesta = client.post(
        "/obligaciones/",
        headers=headers,
        json={
            "nombre_obligacion": "Deuda anterior",
            "tipo_obligacion": "POR_PAGAR",
            "monto_original": "15000.00",
            "fecha_inicio": date.today().isoformat(),
            "fecha_vencimiento": None,
            "descripcion": "Solo registrar"
        }
    )

    assert respuesta.status_code == 201

    assert saldo_cuenta(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("50000.00")

    movimientos = (
        db_session.query(Movimiento)
        .filter(
            Movimiento.id_obligacion
            == respuesta.json()["id_obligacion"]
        )
        .all()
    )

    assert movimientos == []


def test_prestamo_sin_saldo_se_rechaza(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.sin.saldo.inicial@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta con poco saldo",
        "100.00"
    )

    respuesta = client.post(
        "/obligaciones/",
        headers=headers,
        json=datos_creacion(
            "Préstamo imposible",
            "POR_COBRAR",
            cuenta.id_cuenta,
            str(uuid4())
        )
    )

    assert respuesta.status_code == 409

    assert saldo_cuenta(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("100.00")

    listado = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    assert not any(
        o["nombre_obligacion"] == "Préstamo imposible"
        for o in listado.json()["obligaciones"]
    )


def test_gmf_de_salida_inicial(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.gmf.inicial@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta GMF inicial",
        "50000.00"
    )

    respuesta = client.post(
        "/obligaciones/",
        headers=headers,
        json=datos_creacion(
            "Préstamo con GMF",
            "POR_COBRAR",
            cuenta.id_cuenta,
            str(uuid4()),
            gmf=True
        )
    )

    assert respuesta.status_code == 201

    # 50.000 - 10.000 - 40 de GMF
    assert saldo_cuenta(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("39960.00")


def test_abono_no_confunde_capital_inicial(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.capital.mas.abono@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta capital y cobro",
        "50000.00"
    )

    creada = client.post(
        "/obligaciones/",
        headers=headers,
        json=datos_creacion(
            "Préstamo con devolución",
            "POR_COBRAR",
            cuenta.id_cuenta,
            str(uuid4())
        )
    )

    assert creada.status_code == 201

    id_obligacion = creada.json()["id_obligacion"]

    abono = client.post(
        "/obligaciones/abonos",
        headers=headers,
        json={
            "uuid_local": str(uuid4()),
            "id_cuenta": cuenta.id_cuenta,
            "id_obligacion": id_obligacion,
            "monto": "2000.00",
            "fecha_movimiento": date.today().isoformat(),
            "descripcion": "Devolución parcial"
        }
    )

    assert abono.status_code == 200

    assert saldo_cuenta(
        client,
        headers,
        cuenta.id_cuenta
    ) == Decimal("42000.00")

    plan = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    obligacion = next(
        o for o in plan.json()["obligaciones"]
        if o["id_obligacion"] == id_obligacion
    )

    assert Decimal(
        str(obligacion["monto_pendiente"])
    ) == Decimal("8000.00")

    assert Decimal(
        str(obligacion["total_abonado"])
    ) == Decimal("2000.00")


def test_cuenta_ajena_y_datos_incompletos(
    client,
    db_session
):
    usuario1, headers1 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.inicial.dueno@example.com"
    )

    _, headers2 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.inicial.otro@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario1.id_usuario,
        "Cuenta privada",
        "50000.00"
    )

    datos = datos_creacion(
        "Obligación de cuenta ajena",
        "POR_PAGAR",
        cuenta.id_cuenta,
        str(uuid4())
    )

    ajena = client.post(
        "/obligaciones/",
        headers=headers2,
        json=datos
    )

    assert ajena.status_code == 404

    incompleta = client.post(
        "/obligaciones/",
        headers=headers1,
        json={
            **datos,
            "id_cuenta_inicial": None
        }
    )

    assert incompleta.status_code == 422


def test_creacion_requiere_token(client):
    respuesta = client.post(
        "/obligaciones/",
        json={
            "nombre_obligacion": "Sin autorización",
            "tipo_obligacion": "POR_PAGAR",
            "monto_original": "10000.00",
            "fecha_inicio": date.today().isoformat()
        }
    )

    assert respuesta.status_code == 401
