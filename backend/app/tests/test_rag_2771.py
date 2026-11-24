
"""Pruebas de pertinencia del asistente financiero.

Paso 27.7.1.
"""

import json

from copy import deepcopy

import pytest

from fastapi import HTTPException

from app.business.rag_intencion import (
    interpretar_pregunta,
)

from app.business.rag_retrieval_service import (
    _temas_relevantes,
)

from app.business import (
    rag_presentacion_pertinente as presentacion,
)

from app.routers import rag_router

from app.schemas.rag_schema import (
    PreguntaConIA,
)

from app.tests.test_rag_277 import (
    contexto_prueba,
)


PREGUNTA_PENDIENTES = (
    "¿Qué dinero tengo pendiente de recibir "
    "y qué obligaciones tengo pendientes de pagar?"
)

PREGUNTA_COMBINADA = (
    "¿Cuáles son mis ingresos, gastos, "
    "deudas pendientes y metas actuales?"
)


def contexto_ampliado():

    contexto = contexto_prueba()

    contexto["postgresql"]["obligaciones"] = [

        {
            "id_obligacion": 801,
            "nombre": "Deuda saldada privada",
            "tipo": "POR_PAGAR",
            "estado": "SALDADA",
            "pendiente": "0.00",
        },

        {
            "id_obligacion": 802,
            "nombre": "Cobro activo privado",
            "tipo": "POR_COBRAR",
            "estado": "ACTIVA",
            "pendiente": "90000.00",
        },

        {
            "id_obligacion": 803,
            "nombre": "Deuda activa privada",
            "tipo": "POR_PAGAR",
            "estado": "ACTIVA",
            "pendiente": "100000.00",
        },
    ]

    contexto["analisis_financiero"][
        "obligaciones"
    ] = {

        "obligaciones_totales": 3,

        "deudas_propias_saldadas": 1,
        "deudas_propias_activas": 1,

        "cobros_saldados": 0,
        "cobros_activos": 1,

        "monto_pendiente_por_pagar": "100000.00",
        "monto_pendiente_por_cobrar": "90000.00",
    }

    contexto["fuseki"]["comprobaciones"][
        "tipos_obligaciones"
    ]["total_en_fuseki"] = 3

    return contexto


def responder_local(pregunta, contexto=None):

    return (
        presentacion.generar_respuesta_local_pertinente(
            pregunta,
            contexto if contexto is not None
            else contexto_ampliado(),
        )
    )


def test_2771_no_recupera_cuentas_para_deudas():

    temas = _temas_relevantes(
        PREGUNTA_PENDIENTES
    )

    assert temas == {
        "obligaciones"
    }


def test_2771_pendientes_no_muestra_saldadas():

    respuesta = responder_local(
        PREGUNTA_PENDIENTES
    )

    assert (
        "Total pendiente por pagar: $100.000 COP"
        in respuesta
    )

    assert (
        "Total pendiente por cobrar: $90.000 COP"
        in respuesta
    )

    assert "Deuda activa privada" in respuesta
    assert "Cobro activo privado" in respuesta

    assert "Deuda saldada privada" not in respuesta
    assert "SALDADA" not in respuesta
    assert "Saldo libre disponible" not in respuesta
    assert "Caja privada" not in respuesta


def test_2771_diferentes_estados_en_misma_pregunta():

    respuesta = responder_local(
        "¿Cuántas deudas tengo saldadas "
        "y cuánto dinero me deben?"
    )

    assert "Deudas propias saldadas: 1" in respuesta

    assert (
        "Total pendiente por cobrar: $90.000 COP"
        in respuesta
    )

    assert "Total pendiente por pagar:" not in respuesta

    assert "Deuda activa privada" not in respuesta
    assert "Deuda saldada privada" not in respuesta
    assert "Cobro activo privado" not in respuesta


def test_2771_total_por_cobrar_sin_listados():

    respuesta = responder_local(
        "¿Cuánto dinero me deben?"
    )

    assert (
        "Total pendiente por cobrar: $90.000 COP"
        in respuesta
    )

    assert "Cobro activo privado" not in respuesta
    assert "Deudas propias" not in respuesta
    assert "Cobros saldados" not in respuesta
    assert "Cuentas activas" not in respuesta


def test_2771_saldo_disponible_conciso():

    respuesta = responder_local(
        "¿Cuánto dinero tengo disponible?"
    )

    assert (
        "Saldo libre disponible: $650.000 COP"
        in respuesta
    )

    assert "Saldo real total" not in respuesta
    assert "Dinero reservado" not in respuesta
    assert "Caja privada" not in respuesta

    assert "Deudas propias" not in respuesta
    assert "Metas financieras" not in respuesta


def test_2771_combinada_conserva_metas():

    respuesta = responder_local(
        PREGUNTA_COMBINADA
    )

    assert "Ingresos ordinarios: $315.000 COP" in respuesta
    assert "Gastos ordinarios: $296.400 COP" in respuesta

    assert (
        "Total pendiente por pagar: $100.000 COP"
        in respuesta
    )

    assert "Metas financieras" in respuesta
    assert "Meta privada" in respuesta

    assert "Deuda saldada privada" not in respuesta
    assert "Deudas propias saldadas" not in respuesta
    assert "Total pendiente por cobrar" not in respuesta

    assert (
        "Reservas y distribución por metas"
        not in respuesta
    )

    assert "Saldo libre disponible" not in respuesta


def test_2771_general_conserva_dominios():

    respuesta = responder_local(
        "Analiza mi situación financiera "
        "considerando mis cuentas, deudas, "
        "gastos, presupuestos y metas."
    )

    for titulo in (
        "Cuentas y liquidez",
        "Ingresos y gastos",
        "Deudas y dinero por cobrar",
        "Presupuestos",
        "Metas financieras",
        "Reservas y distribución por metas",
    ):

        assert titulo in respuesta

    assert "$650.000 COP" in respuesta
    assert "$90.000 COP" in respuesta
    assert "$100.000 COP" in respuesta

    # En el analisis general no hace falta
    # detallar todas las cuentas y deudas.

    assert "Deuda saldada privada" not in respuesta


def test_2771_reservas_muestra_relaciones():

    respuesta = responder_local(
        "¿Cómo están distribuidas las reservas "
        "de mis metas entre las diferentes cuentas?"
    )

    assert (
        "Total reservado vinculado: $350.000 COP"
        in respuesta
    )

    assert "Meta privada — Caja privada" in respuesta

    assert "Saldo libre disponible" not in respuesta
    assert "Saldo real total" not in respuesta
    assert "Total pendiente por pagar" not in respuesta


def test_2771_filtro_antes_del_limite_de_detalles():

    contexto = contexto_ampliado()

    saldadas = [
        {
            "id_obligacion": indice,

            "nombre": (
                f"Registro saldado {indice}"
            ),

            "tipo": "POR_PAGAR",
            "estado": "SALDADA",
            "pendiente": "0.00",
        }

        for indice in range(1, 26)
    ]

    activa = {
        "id_obligacion": 26,
        "nombre": "Obligación activa visible",
        "tipo": "POR_PAGAR",
        "estado": "ACTIVA",
        "pendiente": "50000.00",
    }

    contexto["postgresql"]["obligaciones"] = [
        *saldadas,
        activa,
    ]

    contexto["analisis_financiero"][
        "obligaciones"
    ] = {

        "obligaciones_totales": 26,

        "deudas_propias_saldadas": 25,
        "deudas_propias_activas": 1,

        "cobros_saldados": 0,
        "cobros_activos": 0,

        "monto_pendiente_por_pagar": "50000.00",
        "monto_pendiente_por_cobrar": "0.00",
    }

    respuesta = responder_local(
        "¿Qué obligaciones tengo "
        "pendientes de pagar?",

        contexto,
    )

    assert "Obligación activa visible" in respuesta

    assert (
        "Total pendiente por pagar: $50.000 COP"
        in respuesta
    )

    assert "Registro saldado" not in respuesta


def test_2771_importe_completo_sin_listar_25_registros():

    contexto = contexto_ampliado()

    contexto["postgresql"]["obligaciones"] = [

        {
            "id_obligacion": indice,
            "nombre": f"Cobro prueba {indice}",
            "tipo": "POR_COBRAR",
            "estado": "ACTIVA",
            "pendiente": "100.00",
        }

        for indice in range(1, 26)
    ]

    contexto["analisis_financiero"][
        "obligaciones"
    ] = {

        "obligaciones_totales": 25,

        "deudas_propias_saldadas": 0,
        "deudas_propias_activas": 0,

        "cobros_saldados": 0,
        "cobros_activos": 25,

        "monto_pendiente_por_pagar": "0.00",
        "monto_pendiente_por_cobrar": "2500.00",
    }

    respuesta = responder_local(
        "¿Cuánto dinero me deben?",
        contexto,
    )

    assert "$2.500 COP" in respuesta

    assert "Cobro prueba" not in respuesta
    assert "20 de 25 registros" not in respuesta


def test_2771_no_calcula_desde_lista_incompleta():

    contexto = contexto_ampliado()

    contexto["analisis_financiero"][
        "obligaciones"
    ]["obligaciones_totales"] = 50

    respuesta = responder_local(
        "¿Cuánto dinero me deben?",
        contexto,
    )

    assert (
        "No se dispone de una lista completa"
        in respuesta
    )

    assert "Total pendiente por cobrar:" not in respuesta


def test_2771_presupuesto_no_activa_cuentas():

    intencion = interpretar_pregunta(
        "¿Cuánto tengo disponible "
        "en mi presupuesto?"
    )

    assert intencion.temas == frozenset({
        "presupuestos"
    })

    assert intencion.secciones == (
        "presupuestos",
    )


def test_2771_metas_activas_filtran_cumplidas():

    contexto = contexto_ampliado()

    contexto["postgresql"]["metas"].append({
        "id_meta": 702,
        "nombre": "Meta cumplida privada",
        "objetivo": "100000.00",
        "acumulado": "100000.00",
        "progreso_porcentaje": "100.00",
        "estado": "CUMPLIDA",
    })

    respuesta = responder_local(
        "¿Cuáles son mis metas activas?",
        contexto,
    )

    assert "Meta privada" in respuesta
    assert "Meta cumplida privada" not in respuesta


def test_2771_gemini_no_recibe_importes_ni_pregunta(
    monkeypatch,
):

    contexto = contexto_ampliado()
    original = deepcopy(contexto)

    recibido = {}

    def generar(
        pregunta,
        evidencia,
        instrucciones,
    ):

        recibido["pregunta"] = pregunta

        recibido["evidencia"] = json.dumps(
            evidencia,
            ensure_ascii=False,
        )

        return json.dumps({
            "orden": evidencia["secciones_permitidas"],
            "foco": [],
        })

    monkeypatch.setattr(
        presentacion.motor.gateway,
        "generar_respuesta_gemini",
        generar,
    )

    respuesta = (
        presentacion.generar_respuesta_pertinente(
            PREGUNTA_PENDIENTES,
            contexto,
        )
    )

    assert "$100.000 COP" in respuesta
    assert "$90.000 COP" in respuesta

    assert "Deuda activa privada" in respuesta

    assert (
        recibido["pregunta"]
        != PREGUNTA_PENDIENTES
    )

    for prohibido in (
        "100000.00",
        "90000.00",
        "Deuda activa privada",
        "Cobro activo privado",
        "id_obligacion",
        "urn:finanzas:grafo",
    ):

        assert prohibido not in recibido[
            "evidencia"
        ]

    assert contexto == original


def test_2771_pregunta_ambigua_no_consulta_fuentes(
    monkeypatch,
):

    monkeypatch.setenv(
        "RAG_IA_HABILITADA",
        "1",
    )

    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "clave-simulada",
    )

    def nunca_llamar(*args, **kwargs):

        raise AssertionError(
            "No se debe consultar sin "
            "una intencion financiera."
        )

    monkeypatch.setattr(
        rag_router,
        "_recuperar",
        nunca_llamar,
    )

    monkeypatch.setattr(
        rag_router,
        "generar_respuesta_rag",
        nunca_llamar,
    )

    class UsuarioSimulado:
        id_usuario = 7

    with pytest.raises(HTTPException) as error:

        rag_router.responder_con_rag(
            PreguntaConIA(
                pregunta="Hola, buenos días",
                autorizo_envio_ia=True,
            ),

            db=object(),

            usuario=UsuarioSimulado(),
        )

    assert error.value.status_code == 422
