from datetime import date
from uuid import uuid4

from app.models import Movimiento

from app.tests.helpers import (
    crear_usuario_autenticado,
    crear_cuenta,
    obtener_categoria_sistema,
)


def crear_categoria_prueba(client, headers, nombre, tipo="GASTO"):
    respuesta = client.post(
        "/categorias/",
        headers=headers,
        json={"nombre_categoria": nombre, "tipo_categoria": tipo},
    )

    assert respuesta.status_code == 201
    return respuesta.json()


def test_editar_categoria_propia(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client, db_session, "editar.categoria@example.com"
    )

    categoria = crear_categoria_prueba(client, headers, "Mascotas test edicion")

    respuesta = client.patch(
        f"/categorias/{categoria['id_categoria']}",
        headers=headers,
        json={"nombre_categoria": "Veterinaria test"},
    )

    assert respuesta.status_code == 200

    datos = respuesta.json()

    assert datos["nombre_categoria"] == "Veterinaria test"
    assert datos["id_usuario"] == usuario.id_usuario
    assert datos["tipo_categoria"] == "GASTO"
    assert datos["es_sistema"] is False
    assert datos["estado"] == "ACTIVA"

    listado = client.get("/categorias/?tipo=GASTO", headers=headers)

    assert listado.status_code == 200
    assert any(
        c["id_categoria"] == categoria["id_categoria"]
        and c["nombre_categoria"] == "Veterinaria test"
        for c in listado.json()
    )


def test_rechazar_duplicado_al_editar(client, db_session):
    _, headers = crear_usuario_autenticado(
        client, db_session, "duplicado.editar@example.com"
    )

    crear_categoria_prueba(client, headers, "Transporte pytest")

    segunda = crear_categoria_prueba(client, headers, "Mascotas pytest")

    respuesta = client.patch(
        f"/categorias/{segunda['id_categoria']}",
        headers=headers,
        json={"nombre_categoria": "  transporte   PYTEST "},
    )

    assert respuesta.status_code == 409


def test_no_editar_ni_desactivar_categoria_ajena(client, db_session):
    _, headers1 = crear_usuario_autenticado(
        client, db_session, "dueno.categoria@example.com"
    )

    _, headers2 = crear_usuario_autenticado(
        client, db_session, "intruso.categoria@example.com"
    )

    categoria = crear_categoria_prueba(client, headers1, "Categoria privada")

    url = f"/categorias/{categoria['id_categoria']}"

    edicion = client.patch(
        url, headers=headers2, json={"nombre_categoria": "Nombre indebido"}
    )

    desactivacion = client.post(url + "/desactivar", headers=headers2)

    assert edicion.status_code == 404
    assert desactivacion.status_code == 404


def test_no_administrar_categoria_del_sistema(client, db_session):
    _, headers = crear_usuario_autenticado(
        client, db_session, "sistema.editar@example.com"
    )

    categoria = obtener_categoria_sistema(db_session, "GASTO")

    url = f"/categorias/{categoria.id_categoria}"

    edicion = client.patch(
        url, headers=headers, json={"nombre_categoria": "Cambio indebido"}
    )

    desactivacion = client.post(url + "/desactivar", headers=headers)

    assert edicion.status_code == 403
    assert desactivacion.status_code == 403


def test_rechazar_campos_no_editables(client, db_session):
    _, headers = crear_usuario_autenticado(
        client, db_session, "campos.categoria@example.com"
    )

    categoria = crear_categoria_prueba(client, headers, "Categoria validacion")

    respuesta = client.patch(
        f"/categorias/{categoria['id_categoria']}",
        headers=headers,
        json={
            "nombre_categoria": "Nuevo nombre",
            "tipo_categoria": "INGRESO",
            "es_sistema": True,
        },
    )

    assert respuesta.status_code == 422


def test_desactivar_conserva_historial(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client, db_session, "historial.categoria@example.com"
    )

    cuenta = crear_cuenta(
        db_session, usuario.id_usuario, "Cuenta historial categorias", "1000.00"
    )

    categoria = crear_categoria_prueba(client, headers, "Gastos historicos pytest")

    movimiento = client.post(
        "/movimientos/normales",
        headers=headers,
        json={
            "uuid_local": str(uuid4()),
            "id_cuenta": cuenta.id_cuenta,
            "id_categoria": categoria["id_categoria"],
            "tipo": "GASTO",
            "monto": "100.00",
            "fecha_movimiento": date.today().isoformat(),
            "descripcion": "Movimiento antes de desactivar",
        },
    )

    assert movimiento.status_code == 200

    id_movimiento = movimiento.json()["id_movimiento"]

    url = f"/categorias/{categoria['id_categoria']}" "/desactivar"

    primera = client.post(url, headers=headers)
    segunda = client.post(url, headers=headers)

    assert primera.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["estado"] == "INACTIVA"

    # El registro financiero original sigue intacto.
    db_session.expire_all()

    existente = db_session.get(Movimiento, id_movimiento)

    assert existente is not None
    assert existente.estado == "ACTIVO"
    assert existente.id_categoria == categoria["id_categoria"]

    # La categoría ya no aparece entre las activas.
    listado = client.get("/categorias/?tipo=GASTO", headers=headers)

    assert listado.status_code == 200
    assert categoria["id_categoria"] not in [c["id_categoria"] for c in listado.json()]

    # Una categoría inactiva no puede editarse.
    edicion = client.patch(
        f"/categorias/{categoria['id_categoria']}",
        headers=headers,
        json={"nombre_categoria": "Cambio posterior"},
    )

    assert edicion.status_code == 409

    # Tampoco debe poder utilizarse para gastos nuevos.
    nuevo = client.post(
        "/movimientos/normales",
        headers=headers,
        json={
            "uuid_local": str(uuid4()),
            "id_cuenta": cuenta.id_cuenta,
            "id_categoria": categoria["id_categoria"],
            "tipo": "GASTO",
            "monto": "10.00",
            "fecha_movimiento": date.today().isoformat(),
            "descripcion": "Uso indebido de categoria inactiva",
        },
    )

    # El código exacto depende de la validación ya existente.
    # Debe ser un rechazo del cliente, nunca un error 500.
    assert nuevo.status_code in (400, 409, 422)


def test_administracion_requiere_token(client):
    edicion = client.patch("/categorias/1", json={"nombre_categoria": "Sin permiso"})

    desactivacion = client.post("/categorias/1/desactivar")

    assert edicion.status_code == 401
    assert desactivacion.status_code == 401
