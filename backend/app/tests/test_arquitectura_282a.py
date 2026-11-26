"""Pruebas de arquitectura y autenticacion.

Paso 28.2 A.
"""

import ast

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from pathlib import Path

from unittest.mock import MagicMock

import jwt
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sqlalchemy.exc import IntegrityError

from app.main import app

from app.business.errores import (
    CodigoError,
    ErrorNegocio,
)

from app.business import (
    auth_business_service as auth_business,
)

from app.routers.errores import (
    manejar_error_negocio,
)

from app.services import (
    auth_service as auth_tecnico,
)

from app.schemas.auth_schema import (
    UsuarioRegistro,
)

from app.persistence.usuario_repository import (
    buscar_usuario_por_id,
)


RAIZ_APP = Path(
    __file__
).resolve().parents[1]


# ========================================
# SEPARACION DE CAPAS
# ========================================

def _modulos_importados(archivo):

    arbol = ast.parse(
        archivo.read_text(
            encoding="utf-8-sig"
        )
    )

    modulos = set()

    for nodo in ast.walk(arbol):

        if isinstance(nodo, ast.Import):

            modulos.update(
                alias.name
                for alias in nodo.names
            )

        elif isinstance(nodo, ast.ImportFrom):

            modulo = nodo.module or ""

            modulos.add(modulo)

            for alias in nodo.names:

                modulos.add(
                    modulo + "." + alias.name
                )

    return modulos


def _pertenece(modulo, prefijo):

    return (
        modulo == prefijo

        or modulo.startswith(
            prefijo + "."
        )
    )


def test_282a_business_no_depende_de_fastapi():

    for archivo in (
        RAIZ_APP / "business"
    ).glob("*.py"):

        importaciones = (
            _modulos_importados(archivo)
        )

        assert not any(

            _pertenece(modulo, "fastapi")

            or _pertenece(modulo, "starlette")

            for modulo in importaciones

        ), archivo.name


@pytest.mark.parametrize(
    "ruta",
    [
        "routers/auth_router.py",
        "dependencies.py",
    ],
)
def test_282a_presentation_no_llama_services(ruta):

    importaciones = _modulos_importados(
        RAIZ_APP / ruta
    )

    assert not any(

        _pertenece(
            modulo,
            "app.services",
        )

        for modulo in importaciones

    )


def test_282a_auth_tecnico_independiente():

    importaciones = _modulos_importados(

        RAIZ_APP
        / "services"
        / "auth_service.py"

    )

    prohibidos = (
        "fastapi",
        "starlette",
        "sqlalchemy",
        "app.business",
        "app.persistence",
        "app.routers",
        "app.models",
        "app.schemas",
    )

    for modulo in importaciones:

        assert not any(

            _pertenece(modulo, prefijo)

            for prefijo in prohibidos

        ), modulo


# ========================================
# TRADUCCION DE EXCEPCIONES
# ========================================

@pytest.mark.parametrize(
    "codigo, estado, bearer",
    [
        (
            CodigoError.AUTENTICACION_REQUERIDA,
            401,
            True,
        ),
        (
            CodigoError.NO_AUTENTICADO,
            401,
            False,
        ),
        (
            CodigoError.PROHIBIDO,
            403,
            False,
        ),
        (
            CodigoError.NO_ENCONTRADO,
            404,
            False,
        ),
        (
            CodigoError.CONFLICTO,
            409,
            False,
        ),
        (
            CodigoError.VALIDACION,
            422,
            False,
        ),
    ],
)
def test_282a_traduccion_error_http(
    codigo,
    estado,
    bearer,
):

    api = FastAPI()

    api.add_exception_handler(
        ErrorNegocio,

        manejar_error_negocio,
    )

    @api.get("/")
    def provocar_error():

        raise ErrorNegocio(
            codigo,

            "Error de prueba",
        )

    with TestClient(api) as cliente:

        respuesta = cliente.get("/")

    assert respuesta.status_code == estado

    assert respuesta.json() == {
        "detail": "Error de prueba",
    }

    if bearer:

        assert (
            respuesta.headers["www-authenticate"]
            == "Bearer"
        )

    else:

        assert (
            "www-authenticate"
            not in respuesta.headers
        )


def test_282a_manejador_registrado():

    assert (

        app.exception_handlers[ErrorNegocio]

        is manejar_error_negocio

    )


# ========================================
# SEGURIDAD JWT
# ========================================

def test_282a_token_valido(monkeypatch):

    monkeypatch.setattr(
        auth_tecnico,

        "SECRET_KEY",

        "a" * 64,
    )

    token = auth_tecnico.crear_access_token(
        123
    )

    assert (
        auth_tecnico.validar_access_token(
            token
        )
        == 123
    )


def test_282a_token_expirado(monkeypatch):

    monkeypatch.setattr(
        auth_tecnico,

        "SECRET_KEY",

        "a" * 64,
    )

    ahora = datetime.now(
        timezone.utc
    )

    token = jwt.encode(
        {
            "sub": "123",

            "iat": ahora - timedelta(
                minutes=60
            ),

            "exp": ahora - timedelta(
                minutes=30
            ),
        },

        auth_tecnico.SECRET_KEY,

        algorithm=auth_tecnico.ALGORITHM,
    )

    with pytest.raises(
        auth_tecnico.TokenInvalido
    ):

        auth_tecnico.validar_access_token(
            token
        )


def test_282a_token_firma_invalida(
    monkeypatch,
):

    monkeypatch.setattr(
        auth_tecnico,

        "SECRET_KEY",

        "a" * 64,
    )

    ahora = datetime.now(
        timezone.utc
    )

    token = jwt.encode(
        {
            "sub": "123",

            "iat": ahora,

            "exp": ahora + timedelta(
                minutes=30
            ),
        },

        "b" * 64,

        algorithm="HS256",
    )

    with pytest.raises(
        auth_tecnico.TokenInvalido
    ):

        auth_tecnico.validar_access_token(
            token
        )


def test_282a_usuario_inexistente(
    monkeypatch,
):

    monkeypatch.setattr(
        auth_business,

        "validar_access_token",

        lambda token: 123,
    )

    monkeypatch.setattr(
        auth_business,

        "buscar_usuario_por_id",

        lambda db, uid: None,
    )

    with pytest.raises(
        ErrorNegocio
    ) as error:

        auth_business.obtener_usuario_actual(
            token="token-simulado",

            db=object(),
        )

    assert (
        error.value.codigo

        == CodigoError.AUTENTICACION_REQUERIDA
    )


# ========================================
# TRANSACCIONES DE REGISTRO
# ========================================

def test_282a_conflicto_registro_revierte(
    monkeypatch,
):

    db = MagicMock()

    db.commit.side_effect = IntegrityError(
        "INSERT",

        {},

        Exception("Conflicto simulado"),
    )

    monkeypatch.setattr(
        auth_business,

        "buscar_usuario_por_email",

        lambda db, email: None,
    )

    monkeypatch.setattr(
        auth_business,

        "generar_hash",

        lambda password: "hash-simulado",
    )

    monkeypatch.setattr(
        auth_business,

        "insertar_usuario",

        lambda *args, **kwargs: object(),
    )

    refrescar = MagicMock()

    monkeypatch.setattr(
        auth_business,

        "refrescar_usuario",

        refrescar,
    )

    datos = UsuarioRegistro(
        nombre_1="Usuario",

        apellido_1="Prueba",

        email="qa.282a@example.com",

        password="PasswordPrueba2026!",
    )

    with pytest.raises(
        ErrorNegocio
    ) as error:

        auth_business.registrar_usuario(
            db,
            datos,
        )

    assert (
        error.value.codigo

        == CodigoError.CONFLICTO
    )

    db.rollback.assert_called_once()

    refrescar.assert_not_called()


# ========================================
# INTEGRACION HTTP + POSTGRESQL
# ========================================

def test_282a_registro_login_y_perfil(
    client,
    db_session,
):

    password = "PasswordPrueba2026!"

    datos = {
        "nombre_1": "Usuario",

        "nombre_2": None,

        "apellido_1": "Arquitectura",

        "apellido_2": None,

        "email": "qa.282a.auth@example.com",

        "password": password,
    }

    registro = client.post(
        "/auth/registro",

        json=datos,
    )

    assert (
        registro.status_code == 201
    ), registro.text

    perfil = registro.json()

    id_usuario = perfil["id_usuario"]

    assert "password" not in perfil

    assert "password_hash" not in perfil

    usuario = buscar_usuario_por_id(
        db_session,

        id_usuario,
    )

    assert usuario is not None

    assert usuario.password_hash != password

    assert auth_tecnico.verificar_password(
        password,

        usuario.password_hash,
    )

    # El registro duplicado conserva HTTP 409.

    duplicado = client.post(
        "/auth/registro",

        json={
            **datos,

            "email": datos["email"].upper(),
        },
    )

    assert duplicado.status_code == 409

    assert duplicado.json() == {
        "detail": "El correo ya está registrado",
    }

    # Una contrasena incorrecta conserva HTTP 401.

    incorrecto = client.post(
        "/auth/login",

        data={
            "username": datos["email"],

            "password": "PasswordIncorrecta!",
        },
    )

    assert incorrecto.status_code == 401

    assert (
        incorrecto.headers["www-authenticate"]
        == "Bearer"
    )

    assert incorrecto.json() == {
        "detail": "Credenciales incorrectas",
    }

    # Inicio de sesion correcto.

    login = client.post(
        "/auth/login",

        data={
            "username": datos["email"].upper(),

            "password": password,
        },
    )

    assert login.status_code == 200

    token = login.json()["access_token"]

    assert login.json()["token_type"] == "bearer"

    assert (
        auth_tecnico.validar_access_token(token)
        == id_usuario
    )

    headers = {
        "Authorization": f"Bearer {token}",
    }

    consulta = client.get(
        "/auth/me",

        headers=headers,
    )

    assert consulta.status_code == 200

    assert consulta.json()["id_usuario"] == id_usuario

    assert "password_hash" not in consulta.json()

    assert client.get(
        "/auth/me"
    ).status_code == 401

    invalido = client.get(
        "/auth/me",

        headers={
            "Authorization": "Bearer token-invalido",
        },
    )

    assert invalido.status_code == 401

    assert (
        invalido.headers["www-authenticate"]
        == "Bearer"
    )