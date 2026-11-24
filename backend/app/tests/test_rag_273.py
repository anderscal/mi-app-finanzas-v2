
"""Pruebas de vigencia RDF: actualización B2."""

import json

from datetime import datetime, timezone

import pytest

from app.routers import rag_router

from app.business.rag_contexto_ia import (
    preparar_contexto_para_ia,
)


REFERENCIA = datetime(
    2026, 11, 22, 12, 0,
    tzinfo=timezone.utc,
)


def test_273_instantanea_reciente():

    resultado = rag_router.evaluar_vigencia_rdf(
        "2026-11-22T11:00:00+00:00",
        REFERENCIA,
    )

    assert resultado == {
        "estado": "RECIENTE",
        "antiguedad_horas": 1.0,
    }


def test_273_instantanea_antigua():

    resultado = rag_router.evaluar_vigencia_rdf(
        "2026-11-20T11:00:00+00:00",
        REFERENCIA,
    )

    assert resultado == {
        "estado": "ANTIGUA",
        "antiguedad_horas": 49.0,
    }


def test_273_limite_24_horas():

    resultado = rag_router.evaluar_vigencia_rdf(
        "2026-11-21T12:00:00+00:00",
        REFERENCIA,
    )

    assert resultado["estado"] == "RECIENTE"
    assert resultado["antiguedad_horas"] == 24.0


@pytest.mark.parametrize(
    "fecha",
    [
        None,
        "fecha-no-valida",
        "2026-11-22T11:00:00",
        "2026-11-22T13:00:00+00:00",
    ],
)
def test_273_fecha_desconocida(fecha):

    resultado = rag_router.evaluar_vigencia_rdf(
        fecha, REFERENCIA,
    )

    assert resultado == {
        "estado": "DESCONOCIDA",
        "antiguedad_horas": None,
    }


def _contexto_simulado():

    return {
        "pregunta": "¿Cuál es mi saldo libre?",
        "periodo": {"anio": 2026, "mes": 11},
        "moneda": "COP",

        "postgresql": {
            "cuentas": [{
                "nombre": "Cuenta privada",
                "tipo": "AHORROS",
                "saldo_real": "100000.00",
                "reservado": "25000.00",
                "saldo_libre": "75000.00",
            }]
        },

        "fuseki": {
            "grafo": "urn:finanzas:grafo:usuario:7",
            "fecha_instantanea": (
                "2026-11-20T11:00:00+00:00"
            ),
            "categorias_semanticas": [],
            "advertencia": "Datos de una instantánea.",
        },

        "fuentes": [
            {
                "origen": "PostgreSQL",
                "tipo": "datos financieros actuales",
            },
            {
                "origen": "Fuseki/SPARQL",
                "tipo": "grafo semántico del usuario",
            },
        ],

        "limitaciones": [],
    }


def test_273_preserva_saldos_sql():

    actualizado = rag_router._anotar_vigencia_contexto(
        _contexto_simulado(),
        REFERENCIA,
    )

    assert (
        actualizado["postgresql"]["cuentas"][0]["saldo_libre"]
        == "75000.00"
    )

    assert actualizado["fuseki"]["vigencia"] == "ANTIGUA"
    assert actualizado["fuseki"]["antiguedad_horas"] == 49.0
    assert actualizado["fuentes"][1]["vigencia"] == "ANTIGUA"


def test_273_gemini_recibe_advertencia():

    actualizado = rag_router._anotar_vigencia_contexto(
        _contexto_simulado(),
        REFERENCIA,
    )

    reducido = preparar_contexto_para_ia(
        actualizado,
    )

    assert (
        "más de 24 horas"
        in reducido["fuseki"]["advertencia"]
    )

    assert reducido["fuseki"]["vigencia"] == "ANTIGUA"

    serializado = json.dumps(
        reducido, ensure_ascii=False,
    )

    assert "urn:finanzas:grafo:usuario:7" not in serializado
    assert "Cuenta privada" not in serializado
    assert "75000.00" in serializado


def test_273_recuperacion_anota_contexto(monkeypatch):

    def recuperar_simulado(db, id_usuario, pregunta):
        assert id_usuario == 7

        contexto = _contexto_simulado()

        contexto["fuseki"]["fecha_instantanea"] = (
            datetime.now(timezone.utc).isoformat()
        )

        return contexto

    monkeypatch.setattr(
        rag_router,
        "construir_contexto_rag",
        recuperar_simulado,
    )

    resultado = rag_router._recuperar(
        None, 7, "¿Cuál es mi saldo libre?",
    )

    assert resultado["fuseki"]["vigencia"] == "RECIENTE"
    assert "vigencia" in resultado["fuentes"][1]
