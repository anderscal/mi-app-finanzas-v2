
"""Regresion de filtros y clasificaciones.

Paso 27.8.
"""

import json

from copy import deepcopy

import pytest

from app.business import (
    rag_presentacion_pertinente as presentacion,
)

from app.tests.test_rag_277 import contexto_prueba


def contexto_operaciones():

    contexto = contexto_prueba()

    contexto["postgresql"]["cuentas"] = [
        {
            "id_cuenta": 1,
            "nombre": "Caja principal",
            "tipo": "AHORROS",
            "saldo_real": "100000.00",
            "reservado": "0.00",
            "saldo_libre": "100000.00",
        },
        {
            "id_cuenta": 2,
            "nombre": "Caja vacia",
            "tipo": "EFECTIVO",
            "saldo_real": "0.00",
            "reservado": "0.00",
            "saldo_libre": "0.00",
        },
        {
            "id_cuenta": 3,
            "nombre": "Caja reservada",
            "tipo": "AHORROS",
            "saldo_real": "20000.00",
            "reservado": "20000.00",
            "saldo_libre": "0.00",
        },
    ]

    contexto["analisis_financiero"]["cuentas"] = {
        "numero_cuentas_activas": 3,
        "saldo_real_total": "120000.00",
        "reservado_total": "20000.00",
        "saldo_libre_total": "100000.00",
    }

    # Orden deliberadamente incorrecto.
    # Business debe clasificar los importes.

    contexto["postgresql"]["gastos_por_categoria"] = [
        {
            "categoria": "Restaurantes",
            "total_incluido_gmf": "16000.00",
        },
        {
            "categoria": "Alimentacion",
            "total_incluido_gmf": "258400.00",
        },
        {
            "categoria": "Transporte",
            "total_incluido_gmf": "22420.00",
        },
    ]

    return contexto


def responder(pregunta, contexto=None):

    if contexto is None:
        contexto = contexto_operaciones()

    return presentacion.generar_respuesta_local_pertinente(
        pregunta,
        contexto,
    )


def test_278op_contar_cuentas_saldo_cero():

    respuesta = responder(
        "¿Cuántas cuentas tengo con saldo en 0?"
    )

    assert (
        "Cuentas activas con saldo real igual a $0 COP: 1"
        in respuesta
    )

    assert "Caja vacia" not in respuesta

    assert "No puedo identificar" not in respuesta


def test_278op_listar_cuentas_saldo_cero():

    respuesta = responder(
        "¿Cuáles de mis cuentas financieras "
        "tienen su saldo en 0 pesos?"
    )

    assert "Caja vacia" in respuesta

    assert "Caja reservada" not in respuesta
    assert "Caja principal" not in respuesta

    assert "No puedo identificar" not in respuesta


def test_278op_saldo_disponible_cero():

    respuesta = responder(
        "¿Cuáles son mis cuentas "
        "con saldo disponible en cero?"
    )

    assert (
        "saldo disponible igual a $0 COP: 2"
        in respuesta
    )

    assert "Caja vacia" in respuesta
    assert "Caja reservada" in respuesta

    assert "Caja principal" not in respuesta


@pytest.mark.parametrize(
    "pregunta, esperadas, excluidas",
    [
        (
            "¿Cuáles cuentas tienen saldo "
            "inferior a 50.000 pesos?",

            ["Caja vacia", "Caja reservada"],
            ["Caja principal"],
        ),
        (
            "¿Cuáles cuentas tienen saldo "
            "superior a 50.000 pesos?",

            ["Caja principal"],
            ["Caja vacia", "Caja reservada"],
        ),
        (
            "¿Cuáles cuentas tienen saldo "
            "mayor o igual a 20.000 pesos?",

            ["Caja principal", "Caja reservada"],
            ["Caja vacia"],
        ),
    ],
)
def test_278op_comparaciones(
    pregunta,
    esperadas,
    excluidas,
):

    respuesta = responder(pregunta)

    for nombre in esperadas:
        assert nombre in respuesta

    for nombre in excluidas:
        assert nombre not in respuesta


@pytest.mark.parametrize(
    "pregunta, orden",
    [
        (
            "¿En qué categorías estoy gastando más?",

            [
                "Alimentacion",
                "Transporte",
                "Restaurantes",
            ],
        ),
        (
            "¿En qué categorías estoy gastando menos?",

            [
                "Restaurantes",
                "Transporte",
                "Alimentacion",
            ],
        ),
    ],
)
def test_278op_clasificacion_categorias(
    pregunta,
    orden,
):

    respuesta = responder(pregunta)

    posiciones = [
        respuesta.index(nombre)
        for nombre in orden
    ]

    assert posiciones == sorted(posiciones)

    assert "$258.400 COP" in respuesta
    assert "$22.420 COP" in respuesta
    assert "$16.000 COP" in respuesta

    assert "No puedo identificar" not in respuesta


@pytest.mark.parametrize(
    "pregunta, importe",
    [
        (
            "¿Cuánto dinero tengo disponible "
            "en Caja principal?",

            "$100.000 COP",
        ),
        (
            "¿Cuánto gasté en Transporte este mes?",

            "$22.420 COP",
        ),
    ],
)
def test_278op_conserva_filtros_por_entidad(
    pregunta,
    importe,
):

    respuesta = responder(pregunta)

    assert importe in respuesta

    assert "No puedo identificar" not in respuesta


def test_278op_ia_y_respaldo_mismo_orden(
    monkeypatch,
):

    contexto = contexto_operaciones()

    original = deepcopy(contexto)

    def generar(
        pregunta,
        evidencia,
        instrucciones,
    ):

        enviado = json.dumps(evidencia)

        assert "Alimentacion" not in enviado
        assert "Transporte" not in enviado
        assert "258400" not in enviado

        return json.dumps({
            "orden": evidencia["secciones_permitidas"],
            "foco": [],
        })

    monkeypatch.setattr(
        presentacion.motor.gateway,
        "generar_respuesta_gemini",
        generar,
    )

    pregunta = (
        "¿En qué categorías estoy gastando más?"
    )

    respuesta_ia = (
        presentacion.generar_respuesta_pertinente(
            pregunta,
            contexto,
        )
    )

    respuesta_local = responder(
        pregunta,
        contexto,
    )

    for respuesta in (
        respuesta_ia,
        respuesta_local,
    ):

        assert (
            respuesta.index("Alimentacion")
            < respuesta.index("Transporte")
            < respuesta.index("Restaurantes")
        )

    assert contexto == original


def test_278op_no_calcula_desde_cuentas_incompletas():

    contexto = contexto_operaciones()

    contexto["analisis_financiero"]["cuentas"][
        "numero_cuentas_activas"
    ] = 100

    respuesta = responder(
        "¿Cuántas cuentas tengo con saldo en 0?",
        contexto,
    )

    assert "No se recuperó evidencia suficiente" in respuesta

    assert (
        "Cuentas activas con saldo real igual a $0 COP: 1"
        not in respuesta
    )


def test_278op_clasificacion_respeta_limite():

    contexto = contexto_operaciones()

    contexto["postgresql"]["gastos_por_categoria"] = [
        {
            "categoria": f"Categoria prueba {i:02d}",
            "total_incluido_gmf": str(i * 1000),
        }
        for i in range(1, 31)
    ]

    respuesta = responder(
        "¿En qué categorías estoy gastando más?",
        contexto,
    )

    assert "Categoria prueba 30" in respuesta
    assert "Categoria prueba 26" in respuesta

    assert "Categoria prueba 25" not in respuesta

    assert "5 de 30 categorías" in respuesta
