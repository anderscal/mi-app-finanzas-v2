
"""Pruebas de resiliencia Gemini: actualización B2."""

import json

from io import BytesIO
from urllib.error import HTTPError, URLError

import pytest

from app.services import rag_ia_service as ia

from app.business.rag_contexto_ia import (
    generar_respuesta_rag,
)


CONTEXTO = {
    "periodo": {"anio": 2026, "mes": 11},
    "moneda": "COP",

    "postgresql": {
        "cuentas": [{
            "nombre": "Nombre privado de cuenta",
            "tipo": "AHORROS",
            "saldo_real": "100000.00",
            "reservado": "25000.00",
            "saldo_libre": "75000.00",
        }]
    },

    "fuseki": {"categorias_semanticas": []},
    "fuentes": [],
    "limitaciones": [],
}


class RespuestaSimulada:

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "Respuesta financiera de prueba"
                    }]
                },
                "finishReason": "STOP",
            }]
        }).encode("utf-8")


def error_http(solicitud, codigo):

    return HTTPError(
        solicitud.full_url,
        codigo,
        "error simulado",
        {},
        BytesIO(b""),
    )


@pytest.fixture(autouse=True)
def entorno_de_prueba(monkeypatch):

    monkeypatch.setenv(
        "GEMINI_API_KEY", "clave-ficticia-de-prueba",
    )

    monkeypatch.setenv(
        "GEMINI_RAG_MODEL", "gemini-3.5-flash-lite",
    )


def test_275_recupera_tras_dos_503(monkeypatch):

    intentos, esperas = [], []

    def responder(solicitud, timeout):
        assert 0 < timeout <= ia.TIMEOUT_INTENTO

        intentos.append(solicitud)

        if len(intentos) <= 2:
            raise error_http(solicitud, 503)

        return RespuestaSimulada()

    monkeypatch.setattr(ia, "urlopen", responder)
    monkeypatch.setattr(ia.time, "sleep", esperas.append)

    resultado = generar_respuesta_rag(
        "¿Cuál es mi saldo?", CONTEXTO,
    )

    assert resultado == "Respuesta financiera de prueba"
    assert len(intentos) == 3
    assert esperas == [1, 2]


def test_275_reporta_503_tras_tres_fallos(monkeypatch):

    intentos, esperas = [], []

    def responder(solicitud, timeout):
        intentos.append(1)
        raise error_http(solicitud, 503)

    monkeypatch.setattr(ia, "urlopen", responder)
    monkeypatch.setattr(ia.time, "sleep", esperas.append)

    with pytest.raises(ia.IANoDisponible) as fallo:

        generar_respuesta_rag(
            "¿Cuánto tengo?", CONTEXTO,
        )

    assert fallo.value.codigo_http == 503
    assert fallo.value.transitorio is True
    assert "3 intento" in str(fallo.value)
    assert len(intentos) == 3
    assert esperas == [1, 2]


@pytest.mark.parametrize("codigo", [429, 401, 403, 404])
def test_275_no_reintenta_errores_no_transitorios(
    monkeypatch, codigo,
):

    intentos, esperas = [], []

    def responder(solicitud, timeout):
        intentos.append(1)
        raise error_http(solicitud, codigo)

    monkeypatch.setattr(ia, "urlopen", responder)
    monkeypatch.setattr(ia.time, "sleep", esperas.append)

    with pytest.raises(ia.IANoDisponible) as fallo:

        generar_respuesta_rag(
            "¿Tengo reservas?", CONTEXTO,
        )

    assert fallo.value.transitorio is False
    assert len(intentos) == 1
    assert esperas == []

    if codigo == 429:
        assert fallo.value.codigo_http == 429


def test_275_reintenta_error_de_red(monkeypatch):

    intentos, esperas = [], []

    def responder(solicitud, timeout):
        intentos.append(1)

        if len(intentos) == 1:
            raise URLError("fallo simulado")

        return RespuestaSimulada()

    monkeypatch.setattr(ia, "urlopen", responder)
    monkeypatch.setattr(ia.time, "sleep", esperas.append)

    resultado = generar_respuesta_rag(
        "¿Tengo reservas?", CONTEXTO,
    )

    assert resultado == "Respuesta financiera de prueba"
    assert len(intentos) == 2
    assert esperas == [1]


def test_275_no_expone_datos_privados_en_logs(
    monkeypatch, caplog,
):

    peticiones = []

    def responder(solicitud, timeout):
        peticiones.append(solicitud)

        if len(peticiones) == 1:
            raise error_http(solicitud, 503)

        return RespuestaSimulada()

    monkeypatch.setattr(ia, "urlopen", responder)
    monkeypatch.setattr(ia.time, "sleep", lambda _: None)

    generar_respuesta_rag(
        "¿Cuánto tengo?", CONTEXTO,
    )

    assert "HTTP 503" in caplog.text
    assert "Nombre privado de cuenta" not in caplog.text
    assert "clave-ficticia-de-prueba" not in caplog.text
    assert "75000.00" not in caplog.text

    cuerpo = peticiones[0].data.decode("utf-8")

    assert "Nombre privado de cuenta" not in cuerpo
    assert "Cuenta 1" in cuerpo
    assert "75000.00" in cuerpo


def test_275_json_invalido_sin_reintentos(monkeypatch):

    class RespuestaInvalida(RespuestaSimulada):

        def read(self):
            return b"no es json"

    intentos, esperas = [], []

    def responder(solicitud, timeout):
        intentos.append(1)
        return RespuestaInvalida()

    monkeypatch.setattr(ia, "urlopen", responder)
    monkeypatch.setattr(ia.time, "sleep", esperas.append)

    with pytest.raises(ia.IANoDisponible) as fallo:

        generar_respuesta_rag(
            "¿Tengo reservas?", CONTEXTO,
        )

    assert "JSON inválida" in str(fallo.value)
    assert fallo.value.transitorio is False
    assert len(intentos) == 1
    assert esperas == []
