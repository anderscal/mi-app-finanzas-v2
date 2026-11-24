
"""Pruebas B2: contexto, privacidad y presupuesto temporal.

No ejecutan consultas reales a Google ni a bases de datos.
"""

import json

from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from app.business import rag_contexto_ia as ctx

from app.services import rag_ia_service as ia


def contexto_prueba():

    return {
        "pregunta": (
            "¿En cuáles cuentas están "
            "las reservas de Compra privada?"
        ),

        "periodo": {"anio": 2026, "mes": 11},
        "moneda": "COP",
        "temas_recuperados": ["cuentas", "metas"],

        "postgresql": {
            "cuentas": [
                {
                    "id_cuenta": 901,
                    "nombre": "Cuenta repetida",
                    "tipo": "AHORROS",
                    "saldo_real": "200000.00",
                    "reservado": "100000.00",
                    "saldo_libre": "100000.00",
                },
                {
                    "id_cuenta": 902,
                    "nombre": "Cuenta repetida",
                    "tipo": "AHORROS",
                    "saldo_real": "150000.00",
                    "reservado": "50000.00",
                    "saldo_libre": "100000.00",
                },
            ],

            "metas": [{
                "id_meta": 903,
                "nombre": "Compra privada",
                "objetivo": "500000.00",
                "acumulado": "150000.00",
                "estado": "ACTIVA",
            }],
        },

        "analisis_financiero": {
            "cuentas": {
                "numero_cuentas_activas": 2,
                "saldo_real_total": "350000.00",
                "reservado_total": "150000.00",
                "saldo_libre_total": "200000.00",
            },

            "reservas": {
                "total_reservado_vinculado": "150000.00",
                "numero_metas_con_reserva": 1,
                "numero_relaciones_meta_cuenta": 2,

                "relaciones_meta_cuenta": [
                    {
                        "id_meta": 903,
                        "id_cuenta": 901,
                        "nombre_meta": "Compra privada",
                        "nombre_cuenta": "Cuenta repetida",
                        "reservado_neto": "100000.00",
                    },
                    {
                        "id_meta": 903,
                        "id_cuenta": 902,
                        "nombre_meta": "Compra privada",
                        "nombre_cuenta": "Cuenta repetida",
                        "reservado_neto": "50000.00",
                    },
                ],
            },
        },

        "fuseki": {
            "grafo": "urn:finanzas:grafo:usuario:99",
            "vigencia": "RECIENTE",
            "antiguedad_horas": 1.5,

            "comprobaciones": {
                "reservas_meta_cuenta": {
                    "coincide_con_postgresql": True,
                    "numero_relaciones_en_fuseki": 2,
                }
            },

            "categorias_semanticas": [],
        },

        "fuentes": [
            {
                "origen": "PostgreSQL",
                "dato_privado": "SECRETO_FUENTE",
            },
            {"origen": "Fuseki/SPARQL"},
        ],

        "limitaciones": ["SECRETO_LIMITACION"],
    }


def contexto_obligaciones():

    obligaciones = [
        {
            "id_obligacion": 1,
            "nombre": "Deuda privada",
            "tipo": "POR_PAGAR",
            "estado": "SALDADA",
            "pendiente": "0.00",
        },
        {
            "id_obligacion": 2,
            "nombre": "Cobro privado",
            "tipo": "POR_COBRAR",
            "estado": "ACTIVA",
            "pendiente": "90000.00",
        },
    ]

    return {
        "moneda": "COP",
        "postgresql": {
            "obligaciones": obligaciones,
        },

        "analisis_financiero": {
            "obligaciones": {
                "obligaciones_totales": 2,
                "deudas_propias_saldadas": 1,
                "cobros_activos": 1,
                "monto_pendiente_por_cobrar": "90000.00",
            }
        },

        "fuseki": {},
    }


def test_b2_conserva_relaciones_con_nombres_duplicados():

    evidencia = ctx.preparar_contexto_para_ia(
        contexto_prueba(),
    )

    relaciones = evidencia[
        "analisis_financiero"
    ]["reservas"]["relaciones_meta_cuenta"]

    assert relaciones == [
        {
            "meta": "Meta 1",
            "cuenta": "Cuenta 1",
            "reservado_neto": "100000.00",
        },
        {
            "meta": "Meta 1",
            "cuenta": "Cuenta 2",
            "reservado_neto": "50000.00",
        },
    ]


def test_b2_no_envia_identificadores_ni_nombres():

    evidencia = ctx.preparar_contexto_para_ia(
        contexto_prueba(),
    )

    texto = json.dumps(
        evidencia, ensure_ascii=False,
    )

    for prohibido in (
        "Compra privada",
        "Cuenta repetida",
        "id_cuenta",
        "id_meta",
        "urn:finanzas:grafo",
        "SECRETO_FUENTE",
        "SECRETO_LIMITACION",
    ):
        assert prohibido not in texto


def test_b2_protege_nombre_escrito_en_pregunta(monkeypatch):

    recibido = {}

    def generar(pregunta, evidencia, instrucciones):
        recibido["pregunta"] = pregunta
        return "Tu Meta 1 tiene dinero reservado."

    monkeypatch.setattr(
        ia, "generar_respuesta_gemini", generar,
    )

    ctx.generar_respuesta_rag(
        "¿Cuánto tiene Compra privada?",
        contexto_prueba(),
    )

    assert (
        recibido["pregunta"]
        == "¿Cuánto tiene Meta 1?"
    )


def test_b2_restauracion_local_de_alias(monkeypatch):

    monkeypatch.setattr(
        ia,
        "generar_respuesta_gemini",
        lambda *args: (
            "Meta 1 tiene $50.000 en Cuenta 2."
        ),
    )

    respuesta = ctx.generar_respuesta_rag(
        "¿Dónde está el dinero reservado?",
        contexto_prueba(),
    )

    assert respuesta == (
        "Compra privada tiene $50.000 "
        "en Cuenta repetida."
    )


def test_b2_preserva_totales_aunque_limite_detalles():

    contexto = contexto_obligaciones()

    contexto["postgresql"]["obligaciones"] = [
        {
            "id_obligacion": i,
            "nombre": f"Obligación privada {i}",
            "tipo": "POR_COBRAR",
            "estado": "ACTIVA",
            "pendiente": "100.00",
        }
        for i in range(1, 26)
    ]

    contexto["analisis_financiero"]["obligaciones"] = {
        "obligaciones_totales": 25,
        "cobros_activos": 25,
        "monto_pendiente_por_cobrar": "2500.00",
    }

    reducido = ctx.preparar_contexto_para_ia(
        contexto,
    )

    assert len(
        reducido["postgresql"]["obligaciones"]
    ) == ctx.MAX_DETALLES

    assert (
        reducido["analisis_financiero"]
        ["obligaciones"]["monto_pendiente_por_cobrar"]
        == "2500.00"
    )

    assert reducido["cobertura_detalles"]["obligaciones"] == {
        "total_registros": 25,
        "registros_enviados": 20,
        "detalle_completo": False,
    }


def test_b2_informa_discrepancia_rdf():

    contexto = contexto_prueba()

    contexto["fuseki"]["comprobaciones"][
        "reservas_meta_cuenta"
    ]["coincide_con_postgresql"] = False

    reducido = ctx.preparar_contexto_para_ia(
        contexto,
    )

    assert (
        reducido["fuseki"]["comprobaciones"]
        ["reservas_meta_cuenta"]["coincide_con_postgresql"]
        is False
    )

    assert (
        reducido["analisis_financiero"]
        ["reservas"]["total_reservado_vinculado"]
        == "150000.00"
    )

    assert any(
        "discrepancia SQL/RDF" in aviso
        for aviso in reducido["limitaciones"]
    )


def test_b2_preparar_no_modifica_contexto_original():

    contexto = contexto_prueba()
    original = deepcopy(contexto)

    ctx.preparar_contexto_para_ia(contexto)

    assert contexto == original


def test_b2_respaldo_reutiliza_contexto_completo():

    respuesta = ctx.respaldo_desde_contexto(
        "¿Cuántas deudas tengo saldadas "
        "y cuánto dinero me deben?",
        contexto_obligaciones(),
    )

    assert "saldadas:** 1" in respuesta
    assert "$90.000 COP" in respuesta


def test_b2_respaldo_rechaza_lista_incompleta():

    contexto = contexto_obligaciones()

    contexto["analisis_financiero"][
        "obligaciones"
    ]["obligaciones_totales"] = 20

    assert ctx.respaldo_desde_contexto(
        "¿Cuántas deudas tengo saldadas?",
        contexto,
    ) is None


def test_b2_presupuesto_temporal_controla_intentos(
    monkeypatch,
):

    reloj = [0.0]
    tiempos = []

    def dormir(segundos):
        reloj[0] += segundos

    monkeypatch.setattr(
        ia,
        "time",
        SimpleNamespace(
            monotonic=lambda: reloj[0],
            sleep=dormir,
        ),
    )

    monkeypatch.setenv(
        "GEMINI_API_KEY", "clave-falsa",
    )

    def responder(solicitud, timeout):

        tiempos.append(timeout)

        reloj[0] += timeout

        raise HTTPError(
            solicitud.full_url,
            503,
            "fallo simulado",
            {},
            BytesIO(b""),
        )

    monkeypatch.setattr(
        ia, "urlopen", responder,
    )

    with pytest.raises(ia.IANoDisponible) as error:

        ia.generar_respuesta_gemini(
            "Pregunta de prueba",
            {},
            "Instrucciones de prueba",
        )

    assert error.value.transitorio is True

    assert tiempos == [10.0, 10.0, 1.0]

    assert reloj[0] == ia.PRESUPUESTO_SEGUNDOS


def test_b2_no_acepta_respuesta_fuera_del_presupuesto(
    monkeypatch,
):

    reloj = [0.0]
    intentos = []

    monkeypatch.setattr(
        ia,
        "time",
        SimpleNamespace(
            monotonic=lambda: reloj[0],
            sleep=lambda _: None,
        ),
    )

    monkeypatch.setenv(
        "GEMINI_API_KEY", "clave-falsa",
    )

    class RespuestaTardia:

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):

            reloj[0] += (
                ia.PRESUPUESTO_SEGUNDOS + 1
            )

            return b'{"candidates": []}'

    def responder(solicitud, timeout):

        intentos.append(timeout)

        return RespuestaTardia()

    monkeypatch.setattr(
        ia, "urlopen", responder,
    )

    with pytest.raises(ia.IANoDisponible) as error:

        ia.generar_respuesta_gemini(
            "Pregunta",
            {},
            "Instrucciones",
        )

    assert error.value.transitorio is True
    assert len(intentos) == 1
    assert "presupuesto" in str(error.value)


def test_b2_protege_categorias_financieras_personalizadas():

    contexto = contexto_prueba()

    contexto["postgresql"]["gastos_por_categoria"] = [{
        "categoria": "Categoría privada especial",
        "total_incluido_gmf": "500.00",
    }]

    contexto["fuseki"]["categorias_semanticas"] = [{
        "nombre": "Categoría privada especial",
        "clase_ontologica": "CategoriaGasto",
    }]

    reducido = ctx.preparar_contexto_para_ia(
        contexto,
    )

    assert (
        reducido["postgresql"]["gastos_por_categoria"][0]["categoria"]
        == reducido["fuseki"]["categorias_semanticas"][0]["nombre"]
        == "Categoría 1"
    )

    assert (
        "Categoría privada especial"
        not in json.dumps(reducido, ensure_ascii=False)
    )
