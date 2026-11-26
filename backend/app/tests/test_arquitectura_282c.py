"""Pruebas de configuracion CORS.

Paso 28.2 C.
No requieren conexiones externas.
"""

import pytest

from app.main import (
    obtener_origenes_cors,
    ORIGENES_LOCALES,
)


def test_282c_origenes_locales(monkeypatch):

    monkeypatch.delenv(
        "CORS_ORIGINS",
        raising=False,
    )

    assert obtener_origenes_cors() == list(
        ORIGENES_LOCALES
    )


def test_282c_origenes_configurados(monkeypatch):

    monkeypatch.setenv(
        "CORS_ORIGINS",

        "https://frontend.example.com,"
        "http://localhost:5500",
    )

    assert obtener_origenes_cors() == [
        "https://frontend.example.com",
        "http://localhost:5500",
    ]


def test_282c_elimina_duplicados(monkeypatch):

    monkeypatch.setenv(
        "CORS_ORIGINS",

        "https://frontend.example.com,"
        "https://frontend.example.com",
    )

    assert obtener_origenes_cors() == [
        "https://frontend.example.com",
    ]


@pytest.mark.parametrize(
    "origen",
    [
        "*",
        "",
        "http://frontend.example.com",
        "https://frontend.example.com/ruta",
        "https://frontend.example.com?dato=1",
        "https://usuario:clave@frontend.example.com",
        "https://frontend.example.com:99999",
    ],
)
def test_282c_rechaza_origen_invalido(
    monkeypatch,
    origen,
):

    monkeypatch.setenv(
        "CORS_ORIGINS",
        origen,
    )

    with pytest.raises(RuntimeError):

        obtener_origenes_cors()