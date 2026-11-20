
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models import Presupuesto

from app.tests.helpers import (
    crear_usuario_autenticado,
    crear_cuenta,
    obtener_categoria_sistema,
)


def datos_presupuesto(
    id_categoria,
    monto="1000.00",
    anio=None,
    mes=None
):
    hoy = date.today()

    return {
        "id_categoria": id_categoria,
        "anio": anio if anio is not None else hoy.year,
        "mes": mes if mes is not None else hoy.month,
        "monto_limite": monto
    }


def crear_presupuesto_prueba(
    client,
    headers,
    id_categoria,
    monto="1000.00"
):
    respuesta = client.post(
        "/presupuestos/",
        headers=headers,
        json=datos_presupuesto(
            id_categoria,
            monto
        )
    )

    assert respuesta.status_code == 201

    return respuesta.json()


def obtener_resumen_presupuesto(
    client,
    headers,
    id_presupuesto
):
    respuesta = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    assert respuesta.status_code == 200

    return next(
        p for p in respuesta.json()["presupuestos"]
        if p["id_presupuesto"] == id_presupuesto
    )


def registrar_gasto(
    client,
    headers,
    id_cuenta,
    id_categoria,
    monto
):
    return client.post(
        "/movimientos/normales",
        headers=headers,
        json={
            "uuid_local": str(uuid4()),
            "id_cuenta": id_cuenta,
            "id_categoria": id_categoria,
            "tipo": "GASTO",
            "monto": monto,
            "fecha_movimiento": date.today().isoformat(),
            "descripcion": "Gasto para presupuesto pytest"
        }
    )


def test_crear_y_consultar_presupuesto(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.crear@example.com"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    creado = crear_presupuesto_prueba(
        client,
        headers,
        categoria.id_categoria,
        "50000.00"
    )

    assert creado["id_usuario"] == usuario.id_usuario
    assert creado["id_categoria"] == categoria.id_categoria
    assert Decimal(
        str(creado["monto_limite"])
    ) == Decimal("50000.00")

    guardado = db_session.get(
        Presupuesto,
        creado["id_presupuesto"]
    )

    assert guardado is not None
    assert guardado.id_usuario == usuario.id_usuario

    listado = client.get(
        "/presupuestos/",
        headers=headers
    )

    assert listado.status_code == 200

    assert any(
        p["id_presupuesto"] == creado["id_presupuesto"]
        for p in listado.json()
    )

    resumen = obtener_resumen_presupuesto(
        client,
        headers,
        creado["id_presupuesto"]
    )

    assert Decimal(
        str(resumen["gastado"])
    ) == Decimal("0.00")

    assert Decimal(
        str(resumen["disponible"])
    ) == Decimal("50000.00")

    assert Decimal(
        str(resumen["porcentaje_usado"])
    ) == Decimal("0.00")


def test_no_duplicar_categoria_y_periodo(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.duplicado@example.com"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    datos = datos_presupuesto(
        categoria.id_categoria
    )

    primera = client.post(
        "/presupuestos/",
        headers=headers,
        json=datos
    )

    segunda = client.post(
        "/presupuestos/",
        headers=headers,
        json=datos
    )

    assert primera.status_code == 201
    assert segunda.status_code == 409

    # Otra mensualidad sí es permitida.
    otro_mes = 1 if datos["mes"] != 1 else 2

    tercera = client.post(
        "/presupuestos/",
        headers=headers,
        json={
            **datos,
            "mes": otro_mes
        }
    )

    assert tercera.status_code == 201


def test_validar_categorias_del_presupuesto(
    client,
    db_session
):
    _, headers1 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.categoria1@example.com"
    )

    _, headers2 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.categoria2@example.com"
    )

    ingreso = obtener_categoria_sistema(
        db_session,
        "INGRESO"
    )

    respuesta_ingreso = client.post(
        "/presupuestos/",
        headers=headers1,
        json=datos_presupuesto(
            ingreso.id_categoria
        )
    )

    assert respuesta_ingreso.status_code == 422

    creada = client.post(
        "/categorias/",
        headers=headers1,
        json={
            "nombre_categoria": "Mascotas presupuesto",
            "tipo_categoria": "GASTO"
        }
    )

    assert creada.status_code == 201

    id_categoria = creada.json()["id_categoria"]

    # El propietario puede presupuestar
    # sus propias categorías.
    propia = client.post(
        "/presupuestos/",
        headers=headers1,
        json=datos_presupuesto(
            id_categoria
        )
    )

    assert propia.status_code == 201

    # Otro usuario no puede utilizar
    # una categoría privada ajena.
    ajena = client.post(
        "/presupuestos/",
        headers=headers2,
        json=datos_presupuesto(
            id_categoria
        )
    )

    assert ajena.status_code == 404

    desactivar = client.post(
        f"/categorias/{id_categoria}/desactivar",
        headers=headers1
    )

    assert desactivar.status_code == 200

    # La categoría inactiva no puede utilizarse
    # para crear un presupuesto nuevo.
    siguiente_mes = (
        1 if date.today().month != 1 else 2
    )

    inactiva = client.post(
        "/presupuestos/",
        headers=headers1,
        json=datos_presupuesto(
            id_categoria,
            mes=siguiente_mes
        )
    )

    assert inactiva.status_code == 409


def test_editar_presupuesto_propio(
    client,
    db_session
):
    _, headers1 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.editar1@example.com"
    )

    _, headers2 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.editar2@example.com"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    creado = crear_presupuesto_prueba(
        client,
        headers1,
        categoria.id_categoria,
        "30000.00"
    )

    id_presupuesto = creado["id_presupuesto"]

    editado = client.patch(
        f"/presupuestos/{id_presupuesto}",
        headers=headers1,
        json={
            "monto_limite": "45000.00"
        }
    )

    assert editado.status_code == 200

    assert Decimal(
        str(editado.json()["monto_limite"])
    ) == Decimal("45000.00")

    assert (
        editado.json()["id_categoria"]
        == creado["id_categoria"]
    )

    assert editado.json()["mes"] == creado["mes"]
    assert editado.json()["anio"] == creado["anio"]

    resumen = obtener_resumen_presupuesto(
        client,
        headers1,
        id_presupuesto
    )

    assert Decimal(
        str(resumen["disponible"])
    ) == Decimal("45000.00")

    # No puede modificar la categoría.
    indebido = client.patch(
        f"/presupuestos/{id_presupuesto}",
        headers=headers1,
        json={
            "monto_limite": "80000.00",
            "id_categoria": categoria.id_categoria
        }
    )

    assert indebido.status_code == 422

    # Tampoco puede editar el presupuesto ajeno.
    ajeno = client.patch(
        f"/presupuestos/{id_presupuesto}",
        headers=headers2,
        json={
            "monto_limite": "99999.00"
        }
    )

    assert ajeno.status_code == 404


def test_gastos_reales_y_anulaciones(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.gastos@example.com"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta para presupuestos",
        "100000.00"
    )

    creado = crear_presupuesto_prueba(
        client,
        headers,
        categoria.id_categoria,
        "1000.00"
    )

    gasto1 = registrar_gasto(
        client,
        headers,
        cuenta.id_cuenta,
        categoria.id_categoria,
        "300.00"
    )

    gasto2 = registrar_gasto(
        client,
        headers,
        cuenta.id_cuenta,
        categoria.id_categoria,
        "150.00"
    )

    assert gasto1.status_code == 200
    assert gasto2.status_code == 200

    resumen = obtener_resumen_presupuesto(
        client,
        headers,
        creado["id_presupuesto"]
    )

    assert Decimal(
        str(resumen["gastado"])
    ) == Decimal("450.00")

    assert Decimal(
        str(resumen["disponible"])
    ) == Decimal("550.00")

    assert Decimal(
        str(resumen["porcentaje_usado"])
    ) == Decimal("45.00")

    # Anular uno de los gastos debe retirarlo
    # del cálculo del presupuesto.
    anular = client.post(
        "/movimientos/"
        f"{gasto1.json()['id_movimiento']}/anular",
        headers=headers
    )

    assert anular.status_code == 200

    actualizado = obtener_resumen_presupuesto(
        client,
        headers,
        creado["id_presupuesto"]
    )

    assert Decimal(
        str(actualizado["gastado"])
    ) == Decimal("150.00")

    assert Decimal(
        str(actualizado["disponible"])
    ) == Decimal("850.00")


def test_aislamiento_de_gastos_entre_usuarios(
    client,
    db_session
):
    usuario1, headers1 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.usuario1@example.com"
    )

    usuario2, headers2 = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.usuario2@example.com"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    cuenta1 = crear_cuenta(
        db_session,
        usuario1.id_usuario,
        "Cuenta presupuesto usuario1",
        "10000.00"
    )

    cuenta2 = crear_cuenta(
        db_session,
        usuario2.id_usuario,
        "Cuenta presupuesto usuario2",
        "10000.00"
    )

    presupuesto1 = crear_presupuesto_prueba(
        client,
        headers1,
        categoria.id_categoria
    )

    presupuesto2 = crear_presupuesto_prueba(
        client,
        headers2,
        categoria.id_categoria
    )

    gasto1 = registrar_gasto(
        client,
        headers1,
        cuenta1.id_cuenta,
        categoria.id_categoria,
        "200.00"
    )

    gasto2 = registrar_gasto(
        client,
        headers2,
        cuenta2.id_cuenta,
        categoria.id_categoria,
        "700.00"
    )

    assert gasto1.status_code == 200
    assert gasto2.status_code == 200

    resumen1 = obtener_resumen_presupuesto(
        client,
        headers1,
        presupuesto1["id_presupuesto"]
    )

    resumen2 = obtener_resumen_presupuesto(
        client,
        headers2,
        presupuesto2["id_presupuesto"]
    )

    assert Decimal(
        str(resumen1["gastado"])
    ) == Decimal("200.00")

    assert Decimal(
        str(resumen2["gastado"])
    ) == Decimal("700.00")

    lista1 = client.get(
        "/presupuestos/",
        headers=headers1
    ).json()

    lista2 = client.get(
        "/presupuestos/",
        headers=headers2
    ).json()

    assert presupuesto2["id_presupuesto"] not in [
        p["id_presupuesto"] for p in lista1
    ]

    assert presupuesto1["id_presupuesto"] not in [
        p["id_presupuesto"] for p in lista2
    ]


def test_validaciones_y_autenticacion(
    client,
    db_session
):
    _, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.presupuesto.validaciones@example.com"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    datos = datos_presupuesto(
        categoria.id_categoria
    )

    casos_invalidos = [
        {"monto_limite": "0.00"},
        {"monto_limite": "-100.00"},
        {"mes": 13},
        {"mes": 0},
        {"anio": 1999},
        {"id_categoria": -1},
        {"id_usuario": 999999},
    ]

    for cambio in casos_invalidos:
        respuesta = client.post(
            "/presupuestos/",
            headers=headers,
            json={
                **datos,
                **cambio
            }
        )

        assert respuesta.status_code == 422

    sin_token = client.post(
        "/presupuestos/",
        json=datos
    )

    assert sin_token.status_code == 401

    listado = client.get("/presupuestos/")

    assert listado.status_code == 401

    edicion = client.patch(
        "/presupuestos/1",
        json={
            "monto_limite": "1000.00"
        }
    )

    assert edicion.status_code == 401
