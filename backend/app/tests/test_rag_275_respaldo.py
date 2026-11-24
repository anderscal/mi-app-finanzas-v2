
"""Respaldo SQL de obligaciones sin consultas redundantes."""

import pytest

from fastapi import HTTPException

from app.business.rag_respuestas_directas import (
    detectar_consulta_obligaciones,
    respuesta_obligaciones,
)

from app.routers import rag_router

from app.schemas.rag_schema import PreguntaConIA

from app.services.rag_ia_service import IANoDisponible


PREGUNTA = (
    "¿Cuántas deudas tengo saldadas "
    "y cuánto dinero me deben?"
)


def obligacion(tipo, estado, pendiente):

    return {
        "tipo_obligacion": tipo,
        "estado": estado,
        "monto_pendiente": pendiente,
    }


def datos_de_prueba():

    return [
        obligacion("POR_PAGAR", "SALDADA", "0.00"),
        obligacion("POR_COBRAR", "SALDADA", "0.00"),
        obligacion("POR_PAGAR", "SALDADA", "0.00"),
        obligacion("POR_COBRAR", "SALDADA", "0.00"),
        obligacion("POR_COBRAR", "ACTIVA", "50000.00"),
        obligacion("POR_COBRAR", "ACTIVA", "10000.00"),
        obligacion("POR_COBRAR", "SALDADA", "0.00"),
        obligacion("POR_PAGAR", "SALDADA", "0.00"),
        obligacion("POR_PAGAR", "ACTIVA", "50000.00"),
        obligacion("POR_COBRAR", "ACTIVA", "30000.00"),
        obligacion("POR_PAGAR", "ACTIVA", "50000.00"),
    ]


def test_275_detecta_pregunta_mixta():

    assert detectar_consulta_obligaciones(
        PREGUNTA,
    ) == (True, True)


def test_275_calcula_tres_deudas_y_noventa_mil():

    respuesta = respuesta_obligaciones(
        PREGUNTA, datos_de_prueba(),
    )

    assert "saldadas:** 3" in respuesta
    assert "$90.000 COP" in respuesta
    assert "3 obligación(es)" in respuesta
    assert "no generada por Gemini" in respuesta


def test_275_excluye_cobros_saldados_y_deudas_activas():

    respuesta = respuesta_obligaciones(
        PREGUNTA, datos_de_prueba(),
    )

    assert "saldadas:** 3" in respuesta
    assert "$100.000 COP" not in respuesta


def test_275_no_se_usa_para_pregunta_de_cuentas():

    assert respuesta_obligaciones(
        "¿Cuánto dinero tengo disponible?",
        datos_de_prueba(),
    ) is None


def test_275_incluye_mas_de_20_obligaciones():

    todas = [
        obligacion("POR_PAGAR", "SALDADA", "0.00")
        for _ in range(25)
    ]

    todas.append(
        obligacion("POR_COBRAR", "ACTIVA", "123.45")
    )

    respuesta = respuesta_obligaciones(
        PREGUNTA, todas,
    )

    assert "saldadas:** 25" in respuesta
    assert "$123,45 COP" in respuesta


def test_275_ignora_inactivas():

    todas = datos_de_prueba() + [
        obligacion("POR_COBRAR", "INACTIVA", "8000.00")
    ]

    respuesta = respuesta_obligaciones(
        PREGUNTA, todas,
    )

    assert "$90.000 COP" in respuesta


@pytest.mark.parametrize(
    "pendiente",
    ["invalido", "-1", "NaN"],
)
def test_275_rechaza_saldos_invalidos(pendiente):

    datos = datos_de_prueba()
    datos[4]["monto_pendiente"] = pendiente

    assert respuesta_obligaciones(
        PREGUNTA, datos,
    ) is None


def test_275_rechaza_estado_inconsistente():

    datos = datos_de_prueba()
    datos[0]["monto_pendiente"] = "10.00"

    assert respuesta_obligaciones(
        PREGUNTA, datos,
    ) is None


def preparar_router(monkeypatch, llamada_gemini):

    monkeypatch.setenv("RAG_IA_HABILITADA", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "clave-falsa-test")

    monkeypatch.setattr(
        rag_router,
        "modelo_gemini",
        lambda: "gemini-3.5-flash-lite",
    )

    llamadas = []

    def recuperar(db, uid, pregunta):

        assert uid == 2

        llamadas.append(uid)

        obligaciones = [
            {
                "tipo": fila["tipo_obligacion"],
                "estado": fila["estado"],
                "pendiente": fila["monto_pendiente"],
            }
            for fila in datos_de_prueba()
        ]

        return {
            "periodo": {"anio": 2026, "mes": 11},
            "moneda": "COP",

            "postgresql": {
                "obligaciones": obligaciones,
            },

            "analisis_financiero": {
                "obligaciones": {
                    "obligaciones_totales": len(obligaciones),
                }
            },

            "fuentes": [],
            "limitaciones": [],
        }

    monkeypatch.setattr(
        rag_router, "_recuperar", recuperar,
    )

    monkeypatch.setattr(
        rag_router,
        "generar_respuesta_rag",
        llamada_gemini,
    )

    return llamadas


class UsuarioSimulado:
    id_usuario = 2


def test_275_router_devuelve_respaldo_en_503(
    monkeypatch,
):

    def falla_gemini(pregunta, contexto):
        raise IANoDisponible(
            "Gemini no disponible por HTTP 503",
            codigo_http=503,
            transitorio=True,
        )

    llamadas = preparar_router(
        monkeypatch, falla_gemini,
    )

    resultado = rag_router.responder_con_rag(
        PreguntaConIA(
            pregunta=PREGUNTA,
            autorizo_envio_ia=True,
        ),
        db=object(),
        usuario=UsuarioSimulado(),
    )

    assert llamadas == [2]
    assert resultado["metodo"] == "CALCULO_SQL_RESPALDO"
    assert resultado["proveedor"] == "FastAPI/PostgreSQL"
    assert resultado["modelo"] is None
    assert "$90.000 COP" in resultado["respuesta"]

    assert [
        fuente["origen"]
        for fuente in resultado["fuentes"]
    ] == ["PostgreSQL"]


def test_275_router_no_oculta_errores_de_modelo(
    monkeypatch,
):

    def falla_gemini(pregunta, contexto):
        raise IANoDisponible(
            "Modelo Gemini no disponible",
            codigo_http=503,
            transitorio=False,
        )

    preparar_router(monkeypatch, falla_gemini)

    with pytest.raises(HTTPException) as error:

        rag_router.responder_con_rag(
            PreguntaConIA(
                pregunta=PREGUNTA,
                autorizo_envio_ia=True,
            ),
            db=object(),
            usuario=UsuarioSimulado(),
        )

    assert error.value.status_code == 503


def test_275_router_mantiene_consentimiento(
    monkeypatch,
):

    def nunca_llamar(pregunta, contexto):
        raise AssertionError(
            "No se debe llamar a Gemini"
        )

    llamadas = preparar_router(
        monkeypatch, nunca_llamar,
    )

    with pytest.raises(HTTPException) as error:

        rag_router.responder_con_rag(
            PreguntaConIA(
                pregunta=PREGUNTA,
                autorizo_envio_ia=False,
            ),
            db=object(),
            usuario=UsuarioSimulado(),
        )

    assert error.value.status_code == 403
    assert llamadas == []
