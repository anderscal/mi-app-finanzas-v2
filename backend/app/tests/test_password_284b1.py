from datetime import (
    datetime,
    timedelta,
    timezone,
)

import hashlib
import json

import pytest

from fastapi.testclient import TestClient

from sqlalchemy import select

from app.main import app

from app.models import TokenRecuperacion

from app.services import auth_service as auth

from app.services import (
    correo_recuperacion_service as correo,
)


EMAIL = "qa.password284@example.com"

ANTERIOR = "PasswordAnterior2026!"

NUEVA = "PasswordNueva2026!"


def datos_nuevos(**extra):

    return {
        "nueva_password": NUEVA,
        "confirmacion_password": NUEVA,
        **extra,
    }


def login(client, password):

    return client.post(
        "/auth/login",

        data={
            "username": EMAIL,
            "password": password,
        },
    )


def headers(token):

    return {
        "Authorization": "Bearer " + token
    }


@pytest.fixture
def cuenta(client):

    r = client.post(
        "/auth/registro",

        json={
            "nombre_1": "Prueba",
            "apellido_1": "Password",
            "email": EMAIL,
            "password": ANTERIOR,
        },
    )

    assert r.status_code == 201, r.text

    r = login(client, ANTERIOR)

    assert r.status_code == 200

    return r.json()["access_token"]


@pytest.fixture
def envios(monkeypatch):

    recibidos = []

    monkeypatch.setattr(
        correo,

        "obtener_configuracion",

        lambda: (
            "dummy",
            "qa@example.com",
            "http://localhost:5500",
        ),
    )

    monkeypatch.setattr(
        correo,

        "enviar_enlace",

        lambda config, email, token:
            recibidos.append((email, token)),
    )

    return recibidos


def solicitar(client, email=EMAIL):

    return client.post(
        "/auth/solicitar-recuperacion",

        json={"email": email},
    )


# ========================================
# PRUEBAS AISLADAS
# ========================================

def test_unit_jwt_version():

    token = auth.crear_access_token(
        123,
        7,
    )

    assert (
        auth.validar_sesion_token(token)
        == (123, 7)
    )

    assert (
        auth.validar_access_token(token)
        == 123
    )


def test_unit_recuperacion_deshabilitada(
    monkeypatch,
):

    monkeypatch.setenv(
        "RECUPERACION_HABILITADA",
        "0",
    )

    with TestClient(app) as cliente:

        assert (
            solicitar(cliente).status_code
            == 503
        )


def test_unit_no_refleja_secretos():

    with TestClient(app) as cliente:

        r = cliente.post(
            "/auth/restablecer-contrasena",

            json={
                "token": "SECRETO_INVALIDO",
                "nueva_password": "CORTA",
            },
        )

    assert r.status_code == 422

    assert "SECRETO_INVALIDO" not in r.text

    assert "CORTA" not in r.text


def test_unit_brevo(monkeypatch):

    capturado = {}

    class Simulado:

        def __init__(self, host, timeout):

            assert host == "api.brevo.com"

            assert timeout == 8

        def request(
            self,
            metodo,
            ruta,
            cuerpo,
            encabezados,
        ):

            capturado.update(
                metodo=metodo,

                ruta=ruta,

                datos=json.loads(cuerpo),

                encabezados=encabezados,
            )

        def getresponse(self):

            return type(
                "Respuesta",

                (),

                {"status": 201},
            )()

        def close(self):

            pass

    monkeypatch.setattr(
        correo,

        "HTTPSConnection",

        Simulado,
    )

    correo.enviar_enlace(
        (
            "dummy",
            "qa@example.com",
            "https://pwa.example.com",
        ),

        EMAIL,

        "a" * 43,
    )

    assert capturado["metodo"] == "POST"

    assert (
        capturado["ruta"]
        == "/v3/smtp/email"
    )

    assert (
        capturado["encabezados"]["api-key"]
        == "dummy"
    )

    assert (
        "https://pwa.example.com/"
        "#/restablecer-contrasena?token="

        in capturado["datos"]["textContent"]
    )


# ========================================
# PRUEBAS DE INTEGRACION
# ========================================

def test_cambio_password(client, cuenta):

    h = headers(cuenta)

    r = client.post(
        "/auth/cambiar-contrasena",

        headers=h,

        json=datos_nuevos(
            password_actual="Incorrecta"
        ),
    )

    assert r.status_code == 422

    r = client.post(
        "/auth/cambiar-contrasena",

        headers=h,

        json=datos_nuevos(
            password_actual=ANTERIOR
        ),
    )

    assert r.status_code == 200, r.text

    assert client.get(
        "/auth/me",
        headers=h,
    ).status_code == 401

    assert login(
        client,
        ANTERIOR,
    ).status_code == 401

    assert login(
        client,
        NUEVA,
    ).status_code == 200


def test_recuperacion_y_limite(
    client,
    db_session,
    cuenta,
    envios,
):

    conocido = solicitar(client)

    desconocido = solicitar(
        client,
        "no.existe@example.com",
    )

    repetido = solicitar(client)

    assert (
        conocido.status_code
        == desconocido.status_code
        == repetido.status_code
        == 202
    )

    assert (
        conocido.json()
        == desconocido.json()
        == repetido.json()
    )

    assert len(envios) == 1

    token = envios[0][1]

    guardado = db_session.scalar(
        select(TokenRecuperacion)
        .where(
            TokenRecuperacion.token_hash
            == hashlib.sha256(
                token.encode()
            ).hexdigest()
        )
    )

    assert guardado is not None

    assert not guardado.usado

    assert guardado.token_hash != token

    r = client.post(
        "/auth/restablecer-contrasena",

        json=datos_nuevos(token=token),
    )

    assert r.status_code == 200, r.text

    assert client.get(
        "/auth/me",

        headers=headers(cuenta),
    ).status_code == 401

    assert login(
        client,
        ANTERIOR,
    ).status_code == 401

    assert login(
        client,
        NUEVA,
    ).status_code == 200

    assert client.post(
        "/auth/restablecer-contrasena",

        json=datos_nuevos(token=token),
    ).status_code == 422


def test_token_vencido(
    client,
    db_session,
    cuenta,
    envios,
):

    assert solicitar(
        client
    ).status_code == 202

    token = envios[0][1]

    fila = db_session.scalar(
        select(TokenRecuperacion)
        .where(
            TokenRecuperacion.token_hash
            == hashlib.sha256(
                token.encode()
            ).hexdigest()
        )
    )

    fila.fecha_expiracion = (
        datetime.now(timezone.utc)
        - timedelta(seconds=1)
    )

    db_session.commit()

    assert client.post(
        "/auth/restablecer-contrasena",

        json=datos_nuevos(token=token),
    ).status_code == 422

    assert login(
        client,
        ANTERIOR,
    ).status_code == 200


def test_confirmacion_no_coincide(
    client,
    cuenta,
    envios,
):

    assert solicitar(
        client
    ).status_code == 202

    token = envios[0][1]

    assert client.post(
        "/auth/restablecer-contrasena",

        json=datos_nuevos(
            token=token,

            confirmacion_password=(
                "OtraPassword2026!"
            ),
        ),
    ).status_code == 422

    assert client.post(
        "/auth/restablecer-contrasena",

        json=datos_nuevos(token=token),
    ).status_code == 200


def test_cambio_invalida_enlaces(
    client,
    cuenta,
    envios,
):

    assert solicitar(
        client
    ).status_code == 202

    token = envios[0][1]

    assert client.post(
        "/auth/cambiar-contrasena",

        headers=headers(cuenta),

        json=datos_nuevos(
            password_actual=ANTERIOR
        ),
    ).status_code == 200

    assert client.post(
        "/auth/restablecer-contrasena",

        json=datos_nuevos(token=token),
    ).status_code == 422