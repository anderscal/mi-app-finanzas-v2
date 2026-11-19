
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from sqlalchemy import func, select

from app.models import (
    Movimiento,
    ObligacionFinanciera,
)

from app.tests.helpers import (
    crear_usuario_autenticado,
    crear_cuenta,
)


@pytest.mark.parametrize(
    "tipo_obligacion,tipo_movimiento",
    [
        ("POR_PAGAR", "GASTO"),
        ("POR_COBRAR", "INGRESO"),
    ]
)
def test_abono_final_idempotente(
    client,
    db_session,
    tipo_obligacion,
    tipo_movimiento
):

    # -----------------------------------
    # PREPARAR USUARIO Y CUENTA
    # -----------------------------------

    correo = (
        f"qa.abono.{tipo_obligacion.lower()}"
        "@example.com"
    )

    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        correo
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta prueba abonos",
        "50000.00"
    )

    # -----------------------------------
    # CREAR OBLIGACION DE PRUEBA
    # -----------------------------------

    obligacion = ObligacionFinanciera(
        id_usuario=usuario.id_usuario,
        nombre_obligacion="Obligación QA",
        tipo_obligacion=tipo_obligacion,
        monto_original=Decimal("10000.00"),
        fecha_inicio=date.today(),
        fecha_vencimiento=None,
        descripcion="QA idempotencia abonos",
        estado="ACTIVA"
    )

    db_session.add(obligacion)
    db_session.commit()

    # -----------------------------------
    # PRIMER ABONO: SALDAR COMPLETAMENTE
    # -----------------------------------

    uuid_abono = uuid4()

    datos = {
        "uuid_local": str(uuid_abono),
        "id_cuenta": cuenta.id_cuenta,
        "id_obligacion": obligacion.id_obligacion,
        "monto": "10000.00",
        "fecha_movimiento": date.today().isoformat(),
        "descripcion": "QA abono final"
    }

    primera = client.post(
        "/obligaciones/abonos",
        headers=headers,
        json=datos
    )

    assert primera.status_code == 200
    assert primera.json()["creado"] is True
    assert primera.json()["tipo"] == tipo_movimiento

    id_movimiento = primera.json()["id_movimiento"]

    # -----------------------------------
    # REINTENTO CON EXACTAMENTE EL MISMO UUID
    # -----------------------------------

    segunda = client.post(
        "/obligaciones/abonos",
        headers=headers,
        json=datos
    )

    assert segunda.status_code == 200
    assert segunda.json()["creado"] is False
    assert segunda.json()["id_movimiento"] == id_movimiento

    assert Decimal(
        str(segunda.json()["monto_pendiente"])
    ) == Decimal("0.00")

    # -----------------------------------
    # VERIFICAR ESTADO E INTEGRIDAD
    # -----------------------------------

    db_session.expire_all()

    actual = db_session.get(
        ObligacionFinanciera,
        obligacion.id_obligacion
    )

    assert actual.estado == "SALDADA"

    cantidad = db_session.scalar(
        select(func.count(Movimiento.id_movimiento))
        .where(
            Movimiento.id_obligacion
            == obligacion.id_obligacion,
            Movimiento.origen == "OBLIGACION"
        )
    )

    assert cantidad == 1

    movimiento = db_session.get(
        Movimiento,
        id_movimiento
    )

    assert movimiento.estado == "ACTIVO"
    assert movimiento.monto == Decimal("10000.00")

    # -----------------------------------
    # UUID NUEVO NO DEBE REGISTRAR OTRO ABONO
    # -----------------------------------

    intento_nuevo = {
        **datos,
        "uuid_local": str(uuid4())
    }

    tercera = client.post(
        "/obligaciones/abonos",
        headers=headers,
        json=intento_nuevo
    )

    assert tercera.status_code == 409

    cantidad_final = db_session.scalar(
        select(func.count(Movimiento.id_movimiento))
        .where(
            Movimiento.id_obligacion
            == obligacion.id_obligacion,
            Movimiento.origen == "OBLIGACION"
        )
    )

    assert cantidad_final == 1
