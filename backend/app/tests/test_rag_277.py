
"""Paso 27.7.

Pruebas del motor de respuestas verificables
y del respaldo financiero general.
"""

import json

from copy import deepcopy

import pytest

from app.business import (
    rag_motor_respuestas as motor,
)

from app.routers import rag_router

from app.schemas.rag_schema import PreguntaConIA

from app.services.rag_ia_service import (
    IANoDisponible,
)


PREGUNTA = (
    "Analiza mi situación financiera actual "
    "considerando mis cuentas, deudas, gastos, "
    "presupuestos y metas."
)


def contexto_prueba():

    return {
        "pregunta": PREGUNTA,

        "periodo": {
            "anio": 2026,
            "mes": 11,
        },

        "moneda": "COP",

        "temas_recuperados": [
            "cuentas",
            "movimientos",
            "obligaciones",
            "presupuestos",
            "metas",
        ],

        "postgresql": {

            "cuentas": [{
                "id_cuenta": 901,
                "nombre": "Caja privada",
                "tipo": "AHORROS",
                "saldo_real": "1000000.00",
                "reservado": "350000.00",
                "saldo_libre": "650000.00",
            }],

            "resumen_mensual": {
                "ingresos_ordinarios": "315000.00",
                "gastos_ordinarios": "296400.00",
                "gmf_total": "453.60",
            },

            "gastos_por_categoria": [{
                "categoria": "Alimentación",
                "total_incluido_gmf": "258400.00",
            }],

            "obligaciones": [
                {
                    "id_obligacion": 801,
                    "nombre": "Deuda privada",
                    "tipo": "POR_PAGAR",
                    "estado": "SALDADA",
                    "pendiente": "0.00",
                },
                {
                    "id_obligacion": 802,
                    "nombre": "Cobro privado",
                    "tipo": "POR_COBRAR",
                    "estado": "ACTIVA",
                    "pendiente": "90000.00",
                },
            ],

            "presupuestos": [{
                "categoria": "Transporte",
                "limite": "80000.00",
                "gastado": "22420.00",
                "disponible": "57580.00",
                "porcentaje_usado": "28.03",
            }],

            "metas": [{
                "id_meta": 701,
                "nombre": "Meta privada",
                "objetivo": "1000000.00",
                "acumulado": "350000.00",
                "progreso_porcentaje": "35.00",
                "estado": "ACTIVA",
            }],
        },

        "analisis_financiero": {

            "cuentas": {
                "numero_cuentas_activas": 1,
                "saldo_real_total": "1000000.00",
                "reservado_total": "350000.00",
                "saldo_libre_total": "650000.00",
            },

            "obligaciones": {
                "obligaciones_totales": 2,
                "deudas_propias_saldadas": 1,
                "deudas_propias_activas": 0,
                "cobros_saldados": 0,
                "cobros_activos": 1,
                "monto_pendiente_por_pagar": "0.00",
                "monto_pendiente_por_cobrar": "90000.00",
            },

            "reservas": {
                "total_reservado_vinculado": "350000.00",
                "numero_metas_con_reserva": 1,
                "numero_relaciones_meta_cuenta": 1,

                "relaciones_meta_cuenta": [{
                    "id_meta": 701,
                    "id_cuenta": 901,
                    "nombre_meta": "Meta privada",
                    "nombre_cuenta": "Caja privada",
                    "reservado_neto": "350000.00",
                }],
            },
        },

        "fuseki": {
            "grafo": "urn:finanzas:grafo:usuario:7",
            "vigencia": "RECIENTE",

            "comprobaciones": {

                "tipos_obligaciones": {
                    "coincide_con_postgresql": True,
                    "total_en_fuseki": 2,
                },

                "reservas_meta_cuenta": {
                    "coincide_con_postgresql": True,
                    "numero_relaciones_en_fuseki": 1,
                },
            },
        },

        "fuentes": [
            {"origen": "PostgreSQL"},
            {"origen": "Fuseki/SPARQL"},
        ],

        "limitaciones": [],
    }


def plan_valido(
    pregunta,
    evidencia,
    instrucciones,
):

    return json.dumps({
        "orden": evidencia["secciones_permitidas"],
        "foco": [],
    })


def test_277_gemini_organiza_sin_calcular(
    monkeypatch,
):

    contexto = contexto_prueba()
    original = deepcopy(contexto)

    def generar(
        pregunta,
        evidencia,
        instrucciones,
    ):
        assert "orden" in instrucciones

        return json.dumps({
            "orden": [
                "obligaciones",
                "cuentas",
                "reservas",
                "metas",
                "presupuestos",
                "movimientos",
            ],

            "foco": [
                "Meta 1",
                "Cuenta 1",
            ],
        })

    monkeypatch.setattr(
        motor.gateway,
        "generar_respuesta_gemini",
        generar,
    )

    respuesta = (
        motor.generar_respuesta_verificable(
            PREGUNTA,
            contexto,
        )
    )

    assert respuesta.index(
        "Deudas y dinero por cobrar"
    ) < respuesta.index(
        "Cuentas y liquidez"
    )

    assert "$650.000 COP" in respuesta
    assert "$90.000 COP" in respuesta
    assert "$350.000 COP" in respuesta

    assert "Meta privada — Caja privada" in respuesta

    assert contexto == original


@pytest.mark.parametrize(
    "texto",
    [
        "No es JSON",

        '{"orden": [], "foco": []}',

        (
            '{"orden": ["cuentas", "cuentas"], '
            '"foco": []}'
        ),

        (
            '{"orden": ["cuentas", "inventado"], '
            '"foco": []}'
        ),

        (
            '{"orden": ["cuentas", "metas"], '
            '"foco": [], "saldo_inventado": 999999}'
        ),

        (
            '{"orden": ["cuentas", "metas"], '
            '"foco": ["Cuenta 999"]}'
        ),
    ],
)
def test_277_rechaza_planes_invalidos(texto):

    bloques = {
        "cuentas": motor.Bloque(
            "Cuentas",

            filas=[
                (
                    ("Cuenta 1",),
                    "Cuenta de prueba",
                )
            ],
        ),

        "metas": motor.Bloque(
            "Metas",
        ),
    }

    with pytest.raises(
        motor.PlanRespuestaInvalido
    ):
        motor.validar_plan(
            texto,
            bloques,
        )


def test_277_plan_preserva_privacidad(
    monkeypatch,
):

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

        return plan_valido(
            pregunta,
            evidencia,
            instrucciones,
        )

    monkeypatch.setattr(
        motor.gateway,
        "generar_respuesta_gemini",
        generar,
    )

    respuesta = (
        motor.generar_respuesta_verificable(
            "¿Dónde está Meta privada?",
            contexto_prueba(),
        )
    )

    assert "Meta privada" not in recibido["pregunta"]
    assert "Meta 1" in recibido["pregunta"]

    for dato in (
        "Meta privada",
        "Caja privada",
        "Cobro privado",
        "id_meta",
        "id_cuenta",
        "urn:finanzas:grafo",
    ):
        assert dato not in recibido["evidencia"]

    assert "Meta privada" in respuesta
    assert "Caja privada" in respuesta


def test_277_respaldo_general_sin_gemini(
    monkeypatch,
):

    def nunca_llamar(*args, **kwargs):
        raise AssertionError(
            "El respaldo no debe llamar a Gemini"
        )

    monkeypatch.setattr(
        motor.gateway,
        "generar_respuesta_gemini",
        nunca_llamar,
    )

    respuesta = (
        motor.generar_respuesta_local(
            PREGUNTA,
            contexto_prueba(),
        )
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

    assert "Resumen financiero local" in respuesta
    assert "$90.000 COP" in respuesta
    assert "$650.000 COP" in respuesta
    assert "$350.000 COP" in respuesta

    assert (
        "coinciden entre PostgreSQL y Fuseki"
        not in respuesta
    )


def test_277_nombres_duplicados_se_distinguen():

    contexto = contexto_prueba()

    cuenta = deepcopy(
        contexto["postgresql"]["cuentas"][0]
    )

    cuenta["id_cuenta"] = 902

    contexto["postgresql"]["cuentas"].append(
        cuenta
    )

    contexto["analisis_financiero"]["cuentas"] = {
        "numero_cuentas_activas": 2,
        "saldo_real_total": "2000000.00",
        "reservado_total": "700000.00",
        "saldo_libre_total": "1300000.00",
    }

    respuesta = (
        motor.generar_respuesta_local(
            PREGUNTA,
            contexto,
        )
    )

    assert "Caja privada (Cuenta 1)" in respuesta
    assert "Caja privada (Cuenta 2)" in respuesta


def test_277_totales_no_se_truncan():

    contexto = contexto_prueba()

    contexto["postgresql"]["obligaciones"] = [
        {
            "id_obligacion": i,
            "nombre": f"Cobro de prueba {i}",
            "tipo": "POR_COBRAR",
            "estado": "ACTIVA",
            "pendiente": "100.00",
        }
        for i in range(1, 26)
    ]

    contexto["analisis_financiero"]["obligaciones"] = {
        "obligaciones_totales": 25,
        "deudas_propias_saldadas": 0,
        "deudas_propias_activas": 0,
        "cobros_saldados": 0,
        "cobros_activos": 25,
        "monto_pendiente_por_pagar": "0.00",
        "monto_pendiente_por_cobrar": "2500.00",
    }

    respuesta = (
        motor.generar_respuesta_local(
            "¿Cuánto dinero me deben?",
            contexto,
        )
    )

    assert "Cobros activos: 25" in respuesta

    assert (
        "Total pendiente por cobrar: $2.500 COP"
        in respuesta
    )

    assert "20 de 25 registros" in respuesta


def test_277_no_oculta_divergencia_semantica(
    monkeypatch,
):

    contexto = contexto_prueba()

    contexto["fuseki"]["comprobaciones"][
        "reservas_meta_cuenta"
    ]["coincide_con_postgresql"] = False

    monkeypatch.setattr(
        motor.gateway,
        "generar_respuesta_gemini",
        plan_valido,
    )

    respuesta = (
        motor.generar_respuesta_verificable(
            PREGUNTA,
            contexto,
        )
    )

    assert "presenta diferencias" in respuesta
    assert "$350.000 COP" in respuesta


def preparar_router(monkeypatch):

    monkeypatch.setenv(
        "RAG_IA_HABILITADA",
        "1",
    )

    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "clave-simulada",
    )

    monkeypatch.setenv(
        "GEMINI_RAG_MODEL",
        "gemini-3.5-flash-lite",
    )

    recuperaciones = []

    def recuperar(
        db,
        id_usuario,
        pregunta,
    ):
        recuperaciones.append(
            id_usuario
        )

        return contexto_prueba()

    monkeypatch.setattr(
        rag_router,
        "_recuperar",
        recuperar,
    )

    return recuperaciones


class UsuarioSimulado:
    id_usuario = 7


@pytest.mark.parametrize(
    "codigo, transitorio",
    [
        (503, True),
        (429, False),
    ],
)
def test_277_router_respaldo_general(
    monkeypatch,
    codigo,
    transitorio,
):

    recuperaciones = preparar_router(
        monkeypatch
    )

    def fallar(*args, **kwargs):

        raise IANoDisponible(
            "Fallo simulado",

            codigo_http=codigo,

            transitorio=transitorio,
        )

    monkeypatch.setattr(
        motor.gateway,
        "generar_respuesta_gemini",
        fallar,
    )

    resultado = rag_router.responder_con_rag(
        PreguntaConIA(
            pregunta=PREGUNTA,
            autorizo_envio_ia=True,
        ),

        db=object(),
        usuario=UsuarioSimulado(),
    )

    assert recuperaciones == [7]

    assert resultado["metodo"] == (
        "CALCULO_SQL_RESPALDO"
    )

    assert resultado["modelo"] is None

    assert resultado["proveedor"] == (
        "FastAPI/PostgreSQL"
    )

    assert "$650.000 COP" in resultado["respuesta"]
    assert "$90.000 COP" in resultado["respuesta"]

    assert "Presupuestos" in resultado["respuesta"]

    assert [
        fuente["origen"]
        for fuente in resultado["fuentes"]
    ] == ["PostgreSQL"]


def test_277_router_rechaza_cifras_del_modelo(
    monkeypatch,
):

    recuperaciones = preparar_router(
        monkeypatch
    )

    monkeypatch.setattr(
        motor.gateway,
        "generar_respuesta_gemini",

        lambda *args: (
            "El usuario tiene $999.999.999 COP "
            "y no tiene deudas."
        ),
    )

    resultado = rag_router.responder_con_rag(
        PreguntaConIA(
            pregunta=PREGUNTA,
            autorizo_envio_ia=True,
        ),

        db=object(),
        usuario=UsuarioSimulado(),
    )

    assert recuperaciones == [7]

    assert resultado["metodo"] == (
        "CALCULO_SQL_RESPALDO"
    )

    assert "999.999.999" not in resultado["respuesta"]

    assert "$650.000 COP" in resultado["respuesta"]

    assert (
        "no superó la validación"
        in resultado["respuesta"]
    )


def test_277_sin_evidencia_no_inventa_resultados():

    respuesta = motor.generar_respuesta_local(
        "¿Cuánto dinero tengo?",

        {
            "postgresql": {},
            "analisis_financiero": {},
            "fuseki": {},
        },
    )

    assert (
        "No se recuperó evidencia suficiente"
        in respuesta
    )

    assert "$0 COP" not in respuesta
