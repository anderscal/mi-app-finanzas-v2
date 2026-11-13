from app.tests.helpers import (
    crear_usuario_autenticado,
    obtener_categoria_sistema,
)


def test_listar_categorias_visibles(client, db_session):
    usuario1, headers1 = crear_usuario_autenticado(
        client, db_session, "categorias.usuario1@example.com"
    )

    _, headers2 = crear_usuario_autenticado(
        client, db_session, "categorias.usuario2@example.com"
    )

    creada = client.post(
        "/categorias/",
        headers=headers1,
        json={"nombre_categoria": "Veterinaria pytest", "tipo_categoria": "GASTO"},
    )

    assert creada.status_code == 201

    id_privada = creada.json()["id_categoria"]

    r1 = client.get("/categorias/", headers=headers1)
    r2 = client.get("/categorias/", headers=headers2)

    assert r1.status_code == 200
    assert r2.status_code == 200

    assert id_privada in [c["id_categoria"] for c in r1.json()]

    assert id_privada not in [c["id_categoria"] for c in r2.json()]

    sistema = obtener_categoria_sistema(db_session, "GASTO")

    assert sistema.id_categoria in [c["id_categoria"] for c in r1.json()]

    assert sistema.id_categoria in [c["id_categoria"] for c in r2.json()]


def test_crear_categoria_personal(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client, db_session, "crear.categoria@example.com"
    )

    respuesta = client.post(
        "/categorias/",
        headers=headers,
        json={"nombre_categoria": "  Cuidado   mascotas  ", "tipo_categoria": "GASTO"},
    )

    assert respuesta.status_code == 201

    datos = respuesta.json()

    assert datos["id_usuario"] == usuario.id_usuario
    assert datos["nombre_categoria"] == "Cuidado mascotas"
    assert datos["tipo_categoria"] == "GASTO"
    assert datos["es_sistema"] is False
    assert datos["estado"] == "ACTIVA"


def test_rechazar_categoria_duplicada(client, db_session):
    _, headers = crear_usuario_autenticado(
        client, db_session, "duplicada.categoria@example.com"
    )

    primera = client.post(
        "/categorias/",
        headers=headers,
        json={"nombre_categoria": " Transporte escolar ", "tipo_categoria": "GASTO"},
    )

    segunda = client.post(
        "/categorias/",
        headers=headers,
        json={"nombre_categoria": "transporte   escolar", "tipo_categoria": "GASTO"},
    )

    assert primera.status_code == 201
    assert segunda.status_code == 409


def test_rechazar_categoria_sistema_duplicada(client, db_session):
    _, headers = crear_usuario_autenticado(
        client, db_session, "sistema.categoria@example.com"
    )

    sistema = obtener_categoria_sistema(db_session, "GASTO")

    respuesta = client.post(
        "/categorias/",
        headers=headers,
        json={"nombre_categoria": sistema.nombre_categoria, "tipo_categoria": "GASTO"},
    )

    assert respuesta.status_code == 409


def test_no_permitir_asignar_propietario(client, db_session):
    usuario, headers = crear_usuario_autenticado(
        client, db_session, "propietario.categoria@example.com"
    )

    respuesta = client.post(
        "/categorias/",
        headers=headers,
        json={
            "nombre_categoria": "Categoría indebida",
            "tipo_categoria": "GASTO",
            "id_usuario": usuario.id_usuario + 1,
            "es_sistema": True,
        },
    )

    assert respuesta.status_code == 422


def test_categorias_requieren_autenticacion(client):
    listado = client.get("/categorias/")

    creacion = client.post(
        "/categorias/",
        json={"nombre_categoria": "Sin permiso", "tipo_categoria": "GASTO"},
    )

    assert listado.status_code == 401
    assert creacion.status_code == 401
