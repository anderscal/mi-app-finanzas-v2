def test_salud(client):

    respuesta = client.get(
        "/salud"
    )

    assert respuesta.status_code == 200

    assert respuesta.json() == {
        "servicio": "FastAPI",
        "estado": "activo"
    }


def test_endpoint_protegido_sin_token(client):

    respuesta = client.get(
        "/auth/me"
    )

    assert respuesta.status_code == 401