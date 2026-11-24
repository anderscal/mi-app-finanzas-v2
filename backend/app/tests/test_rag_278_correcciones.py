
"""Regresion de hallazgos del Paso 27.8.

No requiere llamadas externas ni escrituras financieras.
"""

import json

from copy import deepcopy
from datetime import date

import pytest

from app.business.rag_alcance import (
    resolver_periodo,
    AlcanceNoAdmitido,
)

from app.business import (
    rag_presentacion_pertinente as presentacion,
)

from app.services import (
    rag_ia_service as gateway,
)

from app.tests.test_rag_277 import (
    contexto_prueba,
)


# VALIDACION DE ESTRUCTURAS EXTERNAS

@pytest.mark.parametrize(
    "resultado",
    [
        {"candidates": {}},

        {
            "candidates": [{
                "content": None,
            }]
        },

        {
            "candidates": [{
                "content": {
                    "parts": None,
                }
            }]
        },

        {
            "candidates": [{
                "content": {
                    "parts": "texto inesperado",
                }
            }]
        },
    ],
)
def test_278c_estructura_invalida_controlada(
    resultado,
):

    with pytest.raises(
        gateway.IANoDisponible
    ) as error:

        gateway._extraer_texto(
            resultado
        )

    assert error.value.codigo_http == 503
    assert error.value.transitorio is True


# PERIODOS

@pytest.mark.parametrize(
    "pregunta, hoy, esperado",
    [
        (
            "¿Cuánto gasté en enero de 2025?",
            date(2026, 11, 24),
            (2025, 1),
        ),

        (
            "¿Cuánto gasté el mes pasado?",
            date(2026, 1, 15),
            (2025, 12),
        ),

        (
            "¿Cuánto gasté este mes?",
            date(2026, 11, 24),
            (2026, 11),
        ),
    ],
)
def test_278c_periodos_correctos(
    pregunta,
    hoy,
    esperado,
):

    assert resolver_periodo(
        pregunta,
        hoy,
    ) == esperado


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Cuánto gasté en diciembre de 2027?",

        "¿Cuánto gasté entre enero de 2025 "
        "y febrero de 2025?",

        "¿Cuánto gasté en los últimos 7 días?",
    ],
)
def test_278c_periodos_no_admitidos(
    pregunta,
):

    with pytest.raises(
        AlcanceNoAdmitido
    ):

        resolver_periodo(
            pregunta,
            date(2026, 11, 24),
        )


# CONTEXTO FINANCIERO SIMULADO

def contexto_ampliado():

    contexto = contexto_prueba()

    contexto["postgresql"]["cuentas"].append({
        "id_cuenta": 902,

        "nombre": "Segunda cuenta auditoria",

        "tipo": "AHORROS",

        "saldo_real": "200000.00",

        "reservado": "0.00",

        "saldo_libre": "200000.00",
    })

    contexto["analisis_financiero"]["cuentas"] = {
        "numero_cuentas_activas": 2,

        "saldo_real_total": "1200000.00",

        "reservado_total": "350000.00",

        "saldo_libre_total": "850000.00",
    }

    return contexto


def responder(
    pregunta,
    contexto,
):

    return (
        presentacion.generar_respuesta_local_pertinente(
            pregunta,
            contexto,
        )
    )


# FILTROS SOBRE DATOS COMPLETOS

def test_278c_categoria_fuera_del_limite():

    contexto = contexto_ampliado()

    contexto["postgresql"]["gastos_por_categoria"] = [
        {
            "categoria": f"Categoria prueba {i}",

            "total_incluido_gmf": "50000.00",
        }

        for i in range(1, 26)
    ]

    contexto["postgresql"]["gastos_por_categoria"].append({
        "categoria": "Transporte",

        "total_incluido_gmf": "22420.00",
    })

    respuesta = responder(
        "¿Cuánto gasté en Transporte este mes?",

        contexto,
    )

    assert "Transporte" in respuesta
    assert "$22.420 COP" in respuesta

    assert "$296.400 COP" not in respuesta
    assert "Categoria prueba" not in respuesta


def test_278c_cuenta_especifica_no_es_saldo_global():

    respuesta = responder(
        "¿Cuánto dinero tengo disponible "
        "en Caja privada?",

        contexto_ampliado(),
    )

    assert "Caja privada" in respuesta
    assert "$650.000 COP" in respuesta

    assert "$850.000 COP" not in respuesta
    assert "Segunda cuenta auditoria" not in respuesta


def test_278c_entidad_inexistente_no_inventa_saldo():

    respuesta = responder(
        "¿Cuánto dinero tengo disponible "
        "en Cuenta inexistente?",

        contexto_ampliado(),
    )

    assert "No puedo identificar" in respuesta

    assert "$850.000 COP" not in respuesta
    assert "$0 COP" not in respuesta


def test_278c_nombres_duplicados_no_se_confunden():

    contexto = contexto_ampliado()

    contexto["postgresql"]["cuentas"][1][
        "nombre"
    ] = "Caja privada"

    respuesta = responder(
        "¿Cuánto dinero tengo disponible "
        "en Caja privada?",

        contexto,
    )

    assert "No puedo identificar una única" in respuesta

    assert "$650.000 COP" not in respuesta
    assert "$850.000 COP" not in respuesta


def test_278c_consulta_general_conserva_total():

    respuesta = responder(
        "¿Cuánto dinero tengo disponible "
        "en mis cuentas?",

        contexto_ampliado(),
    )

    assert "$850.000 COP" in respuesta

    assert "No puedo identificar" not in respuesta


def test_278c_ia_y_respaldo_conservan_mismo_filtro(
    monkeypatch,
):

    contexto = contexto_ampliado()

    original = deepcopy(contexto)

    pregunta = (
        "¿Cuánto dinero tengo disponible "
        "en Caja privada?"
    )

    def generar(
        pregunta_ia,
        evidencia,
        instrucciones,
    ):

        serializado = json.dumps(
            evidencia,
            ensure_ascii=False,
        )

        assert "Caja privada" not in pregunta_ia
        assert "Caja privada" not in serializado

        assert "650000" not in serializado
        assert "850000" not in serializado

        return json.dumps({
            "orden": evidencia["secciones_permitidas"],
            "foco": [],
        })

    monkeypatch.setattr(
        gateway,
        "generar_respuesta_gemini",
        generar,
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

        assert "$650.000 COP" in respuesta

        assert "$850.000 COP" not in respuesta

        assert "Caja privada" in respuesta

    assert contexto == original
