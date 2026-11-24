
"""Pruebas RAG PostgreSQL, Fuseki y Gemini.

Actualización B2: preparación del contexto en Business
y transporte HTTP en Services.
"""

import json

from datetime import date
from io import BytesIO
from urllib.error import HTTPError

import pytest

from app.business.rag_retrieval_service import _periodo

from app.business.rag_contexto_ia import (
    generar_respuesta_rag,
    preparar_contexto_para_ia,
)

from app.services.rag_ia_service import (
    IANoDisponible,
    TIMEOUT_INTENTO,
)

from app.tests.helpers import (
    crear_cuenta,
    crear_usuario_autenticado,
)


RUTA = "/consultas/asistente"


def simular_fuseki(monkeypatch):
    consultas = []

    def consultar(consulta):
        consultas.append(consulta)

        if "SELECT ?fecha" in consulta:
            return [{
                "fecha": {
                    "value": "2026-11-22T15:00:00+00:00"
                }
            }]

        if (
            "SELECT ?nombre ?clase" in consulta
            or "SELECT DISTINCT ?nombre ?clase" in consulta
        ):
            return [{
                "nombre": {"value": "Alimentación"},
                "clase": {
                    "value": (
                        "http://www.semanticweb.org/"
                        "user/ontologies/2026/8/"
                        "untitled-ontology-20/"
                        "CategoriaGasto"
                    )
                },
            }]

        raise AssertionError(
            "Consulta SPARQL no reconocida"
        )

    monkeypatch.setattr(
        "app.business.rag_retrieval_service.consultar_select",
        consultar,
    )

    return consultas


def test_271_requiere_autenticacion(client):

    r = client.post(
        f"{RUTA}/contexto",
        json={"pregunta": "¿Cuánto gasté este mes?"},
    )

    assert r.status_code == 401

    r = client.post(
        f"{RUTA}/preguntar",
        json={
            "pregunta": "¿Cuánto gasté este mes?",
            "autorizo_envio_ia": True,
        },
    )

    assert r.status_code == 401


def test_271_contexto_aislado_por_usuario(
    client, db_session, monkeypatch,
):

    u1, h1 = crear_usuario_autenticado(
        client, db_session,
        "qa.rag.271.uno@example.com",
    )

    u2, h2 = crear_usuario_autenticado(
        client, db_session,
        "qa.rag.271.dos@example.com",
    )

    crear_cuenta(
        db_session, u1.id_usuario,
        "Caja RAG Uno", "120000.00",
    )

    crear_cuenta(
        db_session, u2.id_usuario,
        "Caja RAG Dos", "50000.00",
    )

    consultas = simular_fuseki(monkeypatch)

    datos = {
        "pregunta": "¿Cuál es mi saldo disponible?"
    }

    r1 = client.post(
        f"{RUTA}/contexto",
        headers=h1, json=datos,
    )

    r2 = client.post(
        f"{RUTA}/contexto",
        headers=h2, json=datos,
    )

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text

    c1, c2 = r1.json(), r2.json()

    assert [
        x["nombre"]
        for x in c1["postgresql"]["cuentas"]
    ] == ["Caja RAG Uno"]

    assert [
        x["nombre"]
        for x in c2["postgresql"]["cuentas"]
    ] == ["Caja RAG Dos"]

    assert c1["fuentes"][0]["origen"] == "PostgreSQL"
    assert c1["fuentes"][1]["origen"] == "Fuseki/SPARQL"

    for usuario in (u1, u2):
        assert any(
            f"GRAPH <urn:finanzas:grafo:usuario:{usuario.id_usuario}>"
            in consulta
            for consulta in consultas
        )


def test_271_no_envia_a_ia_sin_consentimiento(
    client, db_session, monkeypatch,
):

    _, headers = crear_usuario_autenticado(
        client, db_session,
        "qa.rag.271.consentimiento@example.com",
    )

    monkeypatch.setenv("RAG_IA_HABILITADA", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "clave-simulada")

    r = client.post(
        f"{RUTA}/preguntar",
        headers=headers,
        json={
            "pregunta": "¿Cómo van mis finanzas?",
            "autorizo_envio_ia": False,
        },
    )

    assert r.status_code == 403


def test_271_ia_desactivada(
    client, db_session, monkeypatch,
):

    _, headers = crear_usuario_autenticado(
        client, db_session,
        "qa.rag.271.desactivada@example.com",
    )

    monkeypatch.setenv("RAG_IA_HABILITADA", "0")

    r = client.post(
        f"{RUTA}/preguntar",
        headers=headers,
        json={
            "pregunta": "¿Cómo van mis finanzas?",
            "autorizo_envio_ia": True,
        },
    )

    assert r.status_code == 503


def test_271_gemini_sin_clave(
    client, db_session, monkeypatch,
):

    _, headers = crear_usuario_autenticado(
        client, db_session,
        "qa.rag.271.sinclave@example.com",
    )

    monkeypatch.setenv("RAG_IA_HABILITADA", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    r = client.post(
        f"{RUTA}/preguntar",
        headers=headers,
        json={
            "pregunta": "¿Cuánto gasté este mes?",
            "autorizo_envio_ia": True,
        },
    )

    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.json()["detail"]


def test_271_generacion_recibe_evidencia(
    client, db_session, monkeypatch,
):

    usuario, headers = crear_usuario_autenticado(
        client, db_session,
        "qa.rag.271.generacion@example.com",
    )

    crear_cuenta(
        db_session, usuario.id_usuario,
        "Cuenta RAG", "75000.00",
    )

    consultas = simular_fuseki(monkeypatch)

    monkeypatch.setenv("RAG_IA_HABILITADA", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "clave-simulada")
    monkeypatch.setenv(
        "GEMINI_RAG_MODEL",
        "gemini-2.5-flash-lite",
    )

    recibido = {}

    def modelo_simulado(pregunta, contexto):
        recibido["pregunta"] = pregunta
        recibido["contexto"] = contexto
        return "Tienes $75.000 disponibles. Fuente: PostgreSQL."

    monkeypatch.setattr(
        "app.routers.rag_router.generar_respuesta_rag",
        modelo_simulado,
    )

    r = client.post(
        f"{RUTA}/preguntar",
        headers=headers,
        json={
            "pregunta": "¿Cuánto dinero tengo disponible?",
            "autorizo_envio_ia": True,
        },
    )

    assert r.status_code == 200, r.text

    datos = r.json()

    assert datos["metodo"] == "RAG_SQL_SPARQL"
    assert datos["proveedor"] == "Google Gemini"
    assert datos["modelo"] == "gemini-2.5-flash-lite"
    assert "75.000" in datos["respuesta"]

    contexto = recibido["contexto"]

    assert (
        contexto["postgresql"]["cuentas"][0]["saldo_libre"]
        == "75000.00"
    )

    assert set(contexto["temas_recuperados"]) == {"cuentas"}

    assert (
        contexto["analisis_financiero"]["cuentas"]["saldo_libre_total"]
        == "75000.00"
    )

    assert contexto["fuseki"]["categorias_consultadas"] is False
    assert contexto["fuseki"]["categorias_semanticas"] == []

    assert contexto["fuseki"]["grafo"] == (
        f"urn:finanzas:grafo:usuario:{usuario.id_usuario}"
    )

    assert (
        contexto["fuseki"]["fecha_instantanea"]
        == "2026-11-22T15:00:00+00:00"
    )

    assert len(consultas) == 1
    assert "SELECT ?fecha" in consultas[0]

    assert not any(
        "SELECT ?nombre ?clase" in q
        or "SELECT DISTINCT ?nombre ?clase" in q
        for q in consultas
    )


def test_271_reconoce_mes_pasado():

    hoy = date(2026, 1, 15)

    assert _periodo(
        "¿Cuánto gasté el mes pasado?", hoy,
    ) == (2025, 12)

    assert _periodo(
        "¿Cuánto gasté este mes?", hoy,
    ) == (2026, 1)


def test_271_gemini_generate_content_simulado(
    monkeypatch,
):

    monkeypatch.setenv(
        "GEMINI_API_KEY", "clave-ficticia-prueba",
    )

    monkeypatch.setenv(
        "GEMINI_RAG_MODEL", "gemini-2.5-flash-lite",
    )

    enviado = {}

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
                            "text": "Tu saldo disponible es $75.000."
                        }]
                    },
                    "finishReason": "STOP",
                }]
            }).encode("utf-8")

    def urlopen_simulado(solicitud, timeout):
        enviado["url"] = solicitud.full_url

        enviado["clave"] = solicitud.get_header(
            "X-goog-api-key"
        )

        enviado["cuerpo"] = json.loads(
            solicitud.data.decode("utf-8")
        )

        assert 0 < timeout <= TIMEOUT_INTENTO

        return RespuestaSimulada()

    monkeypatch.setattr(
        "app.services.rag_ia_service.urlopen",
        urlopen_simulado,
    )

    contexto = {
        "periodo": {"anio": 2026, "mes": 11},
        "moneda": "COP",

        "postgresql": {
            "cuentas": [{
                "nombre": "Cuenta académica",
                "tipo": "AHORROS",
                "saldo_real": "100000.00",
                "reservado": "25000.00",
                "saldo_libre": "75000.00",
            }]
        },

        "fuseki": {
            "grafo": "urn:finanzas:grafo:usuario:7",
            "fecha_instantanea": "2026-11-22T15:00:00",
            "categorias_semanticas": [],
        },

        "fuentes": [],
        "limitaciones": [],
    }

    texto = generar_respuesta_rag(
        "¿Cuál es mi saldo libre?",
        contexto,
    )

    assert texto == "Tu saldo disponible es $75.000."

    assert enviado["url"].endswith(
        "/gemini-2.5-flash-lite:generateContent"
    )

    assert enviado["clave"] == "clave-ficticia-prueba"

    cuerpo = enviado["cuerpo"]

    assert "systemInstruction" in cuerpo
    assert cuerpo["contents"][0]["role"] == "user"
    assert cuerpo["generationConfig"]["temperature"] == 0.2

    contenido = cuerpo["contents"][0]["parts"][0]["text"]

    assert "75000.00" in contenido
    assert "urn:finanzas:grafo:usuario:7" not in contenido
    assert "Cuenta académica" not in contenido


def test_271_pregunta_vacia_rechazada(
    client, db_session,
):

    _, headers = crear_usuario_autenticado(
        client, db_session,
        "qa.rag.271.vacia@example.com",
    )

    r = client.post(
        f"{RUTA}/contexto",
        headers=headers,
        json={"pregunta": "  "},
    )

    assert r.status_code == 422


def test_271_gemini_controla_limite_429(
    monkeypatch,
):

    monkeypatch.setenv(
        "GEMINI_API_KEY", "clave-simulada",
    )

    def simular_limite(solicitud, timeout):
        raise HTTPError(
            solicitud.full_url,
            429,
            "Too Many Requests",
            {},
            BytesIO(b""),
        )

    monkeypatch.setattr(
        "app.services.rag_ia_service.urlopen",
        simular_limite,
    )

    with pytest.raises(IANoDisponible) as fallo:

        generar_respuesta_rag(
            "¿Cuánto dinero tengo?",
            {"postgresql": {}, "fuseki": {}},
        )

    assert fallo.value.codigo_http == 429
    assert fallo.value.transitorio is False
    assert "límite" in str(fallo.value)


def test_271_contexto_ia_omite_identificadores():

    contexto = {
        "periodo": {"anio": 2026, "mes": 11},
        "moneda": "COP",

        "postgresql": {

            "cuentas": [{
                "nombre": "Cuenta familiar privada",
                "tipo": "AHORROS",
                "saldo_real": "900.00",
                "reservado": "300.00",
                "saldo_libre": "600.00",
            }],

            "metas": [{
                "nombre": "Meta personal privada",
                "objetivo": "1000.00",
                "acumulado": "300.00",
                "estado": "ACTIVA",
            }],
        },

        "fuseki": {
            "grafo": "urn:finanzas:grafo:usuario:99",
            "fecha_instantanea": "2026-11-22T15:00:00",
            "categorias_semanticas": [],
        },

        "fuentes": [],
        "limitaciones": [],
    }

    reducido = preparar_contexto_para_ia(contexto)

    serializado = json.dumps(
        reducido, ensure_ascii=False,
    )

    assert "Cuenta familiar privada" not in serializado
    assert "Meta personal privada" not in serializado
    assert "urn:finanzas:grafo:usuario:99" not in serializado
    assert "600.00" in serializado

    assert (
        reducido["postgresql"]["cuentas"][0]["nombre"]
        == "Cuenta 1"
    )
