import base64
import io
import ssl

from urllib.request import (
    Request,
    HTTPSHandler,
)

import pytest

from rdflib import Graph

from app.persistence import database

from app.persistence import fuseki_client as fuseki


@pytest.fixture(autouse=True)
def entorno_fuseki(monkeypatch):

    monkeypatch.setenv(
        "FUSEKI_BASE_URL",
        "http://127.0.0.1:3030",
    )

    monkeypatch.setenv(
        "FUSEKI_USER",
        "",
    )

    monkeypatch.setenv(
        "FUSEKI_PASSWORD",
        "",
    )


def remoto(monkeypatch):

    monkeypatch.setenv(
        "FUSEKI_BASE_URL",
        "https://fuseki.example.com",
    )

    monkeypatch.setenv(
        "FUSEKI_USER",
        "fp_backend",
    )

    monkeypatch.setenv(
        "FUSEKI_PASSWORD",
        "a" * 64,
    )


# ======================================
# POSTGRESQL
# ======================================

@pytest.mark.parametrize(

    "host",

    [
        "localhost",
        "127.0.0.1",
        "::1",
    ],
)
def test_db_local(host):

    url = database.crear_url_postgresql({

        "DB_HOST": host,

    })

    assert url.query["sslmode"] == "prefer"

    assert "sslrootcert" not in url.query


def test_db_remota():

    url = database.crear_url_postgresql({

        "DB_HOST": "postgres.example.com",

        "DB_PASSWORD": "a@b:/c",

    })


    assert (

        url.query["sslmode"]

        == "verify-full"
    )

    assert (

        url.query["channel_binding"]

        == "require"
    )

    assert (

        url.query["gssencmode"]

        == "disable"
    )

    assert url.query["sslrootcert"]

    assert url.password == "a@b:/c"


# ======================================
# FUSEKI LOCAL Y REMOTO
# ======================================

def test_fuseki_local():

    assert fuseki._configuracion() == (

        "http://127.0.0.1:3030/finanzas_demo",

        None,
    )


def test_fuseki_remoto(monkeypatch):

    remoto(monkeypatch)

    base, auth = fuseki._configuracion()

    assert (

        base

        == "https://fuseki.example.com/finanzas_demo"
    )

    assert auth == "Basic " + base64.b64encode(

        ("fp_backend:" + "a" * 64).encode()

    ).decode()


# ======================================
# RECHAZO DE URL INSEGURAS
# ======================================

@pytest.mark.parametrize(

    "url",

    [

        "http://fuseki.example.com",

        "ftp://fuseki.example.com",

        "https://user:pass@fuseki.example.com",

        "https://fuseki.example.com/path",

        "https://fuseki.example.com?x=1",

        "https://fuseki.example.com#x",

        "https://fuseki.example.com:0",

    ],
)
def test_rechazar_url(monkeypatch, url):

    remoto(monkeypatch)

    monkeypatch.setenv(
        "FUSEKI_BASE_URL",
        url,
    )

    with pytest.raises(ValueError):

        fuseki._configuracion()


def test_remoto_sin_credenciales(monkeypatch):

    monkeypatch.setenv(

        "FUSEKI_BASE_URL",

        "https://fuseki.example.com",
    )

    with pytest.raises(ValueError):

        fuseki._configuracion()


def test_local_no_envia_secretos(monkeypatch):

    monkeypatch.setenv(

        "FUSEKI_PASSWORD",

        "a" * 64,
    )

    with pytest.raises(ValueError):

        fuseki._configuracion()


# ======================================
# PROTECCION DE REDIRECCIONES
# ======================================

def test_no_redireccion():

    assert fuseki.SinRedireccion().redirect_request(

        None,

        None,

        302,

        "Found",

        {},

        "https://otro.example.com",

    ) is None


# ======================================
# CONSULTAS Y PUBLICACION AUTENTICADAS
# ======================================

def test_solicitudes_autenticadas(monkeypatch):

    remoto(monkeypatch)

    llamadas = []


    class Cliente:

        def open(self, solicitud, timeout):

            llamadas.append(solicitud)

            assert timeout == 12

            return io.BytesIO(

                b'{"results":{"bindings":[]}}'
            )


    def abrir(*handlers):

        contexto = next(

            h._context

            for h in handlers

            if isinstance(h, HTTPSHandler)
        )


        assert contexto.check_hostname

        assert (

            contexto.verify_mode

            == ssl.CERT_REQUIRED
        )


        return Cliente()


    monkeypatch.setattr(

        fuseki,

        "build_opener",

        abrir,
    )


    assert fuseki.consultar_select(

        "SELECT * WHERE {}"

    ) == []


    fuseki.publicar_grafo(

        Graph(),

        "urn:qa:prueba",
    )


    assert [

        r.get_method()

        for r in llamadas

    ] == ["POST", "PUT"]


    for solicitud in llamadas:

        assert solicitud.get_header(

            "Authorization"

        ).startswith("Basic ")


    assert (

        "graph=urn%3Aqa%3Aprueba"

        in llamadas[1].full_url
    )


def test_destino_diferente(monkeypatch):

    remoto(monkeypatch)

    with pytest.raises(ValueError):

        fuseki._solicitar(

            Request(

                "https://otro.example.com/"
                "finanzas_demo/sparql"
            )
        )   