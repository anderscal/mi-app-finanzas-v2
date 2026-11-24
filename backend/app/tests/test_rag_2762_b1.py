
"""Pruebas del Paso 27.6.2 B1.

Recuperación selectiva y reutilización de evidencia.
No llaman a Gemini ni a bases de datos externas.
"""

from decimal import Decimal

from app.business import (
    planificacion_service as plan,
)

from app.business import (
    rag_retrieval_service as rag,
)

from app.business import (
    rag_relaciones_276 as rel,
)

from app.persistence.rag_semantico_basico_repository import (
    obtener_contexto_semantico_basico,
)


def no_llamar(*args, **kwargs):
    raise AssertionError(
        "Se ejecutó una consulta innecesaria"
    )


def semantica_simulada(
    id_usuario,
    incluir_categorias,
):
    return {
        "grafo": f"urn:finanzas:grafo:usuario:{id_usuario}",
        "fecha_instantanea": "2026-11-24T10:00:00Z",
        "categorias_consultadas": incluir_categorias,
        "categorias_semanticas": [],
    }


def test_b1_planificacion_selectiva(monkeypatch):

    monkeypatch.setattr(
        plan,
        "obtener_presupuestos",
        no_llamar,
    )

    monkeypatch.setattr(
        plan,
        "obtener_metas",
        no_llamar,
    )

    monkeypatch.setattr(
        plan,
        "obtener_obligaciones",
        lambda db, uid: [],
    )

    resultado = plan.consultar_planificacion(
        None,
        7,
        temas={"obligaciones"},
    )

    assert resultado["obligaciones"] == []


def test_b1_deudas_no_consultan_cuentas():

    temas = rag._temas_relevantes(
        "Cuántas deudas tengo saldadas "
        "y cuánto dinero me deben"
    )

    assert temas == {"obligaciones"}


def test_b1_reservas_requieren_metas_y_cuentas():

    temas = rag._temas_relevantes(
        "Cuánto dinero tengo reservado "
        "y en cuáles metas"
    )

    assert temas == {
        "cuentas",
        "metas",
    }


def test_b1_deudas_no_consultan_otros_modulos(
    monkeypatch,
):

    llamadas = []

    def plan_simulado(db, uid, temas=None):
        llamadas.append(temas)

        return {
            "obligaciones": [{
                "id_obligacion": 1,
                "nombre_obligacion": "Prueba",
                "tipo_obligacion": "POR_COBRAR",
                "monto_pendiente": Decimal("50000"),
                "estado": "ACTIVA",
            }],
        }

    monkeypatch.setattr(
        rag,
        "consultar_planificacion",
        plan_simulado,
    )

    monkeypatch.setattr(
        rag,
        "obtener_cuentas_con_saldo",
        no_llamar,
    )

    monkeypatch.setattr(
        rag,
        "obtener_aportes_vinculados",
        no_llamar,
    )

    monkeypatch.setattr(
        rag,
        "obtener_movimientos_mes",
        no_llamar,
    )

    monkeypatch.setattr(
        rag,
        "_datos_sparql",
        semantica_simulada,
    )

    contexto = rag.construir_contexto_rag(
        None,
        7,
        "Cuánto dinero me deben",
    )

    assert llamadas == [
        {"obligaciones"}
    ]

    assert "cuentas" not in contexto["postgresql"]

    assert (
        contexto["fuseki"]["categorias_consultadas"]
        is False
    )


def test_b1_obligaciones_no_se_consultan_dos_veces(
    monkeypatch,
):

    monkeypatch.setattr(
        rel,
        "consultar_planificacion",
        no_llamar,
    )

    monkeypatch.setattr(
        rel,
        "_consultar_tipos_obligacion_rdf",
        lambda uid: {
            ("POR_COBRAR", "ACTIVA"): 1
        },
    )

    contexto = {
        "temas_recuperados": ["obligaciones"],

        "postgresql": {
            "obligaciones": [{
                "tipo": "POR_COBRAR",
                "estado": "ACTIVA",
                "pendiente": "50000.00",
            }],
        },

        "fuseki": {},
        "limitaciones": [],
    }

    resultado = rel.enriquecer_contexto_276(
        None,
        7,
        contexto,
    )

    resumen = resultado[
        "analisis_financiero"
    ]["obligaciones"]

    assert (
        resumen["monto_pendiente_por_cobrar"]
        == "50000.00"
    )

    assert (
        resultado["fuseki"]["comprobaciones"]
        ["tipos_obligaciones"]
        ["coincide_con_postgresql"]
        is True
    )


def test_b1_conserva_25_obligaciones(
    monkeypatch,
):

    obligaciones = [
        {
            "id_obligacion": indice,
            "nombre_obligacion": f"Prueba {indice}",
            "tipo_obligacion": "POR_PAGAR",
            "monto_pendiente": Decimal("0.00"),
            "estado": "SALDADA",
        }
        for indice in range(1, 26)
    ]

    monkeypatch.setattr(
        rag,
        "consultar_planificacion",
        lambda *args, **kwargs: {
            "obligaciones": obligaciones
        },
    )

    monkeypatch.setattr(
        rag,
        "_datos_sparql",
        semantica_simulada,
    )

    contexto = rag.construir_contexto_rag(
        None,
        7,
        "Cuántas deudas saldadas tengo",
    )

    assert len(
        contexto["postgresql"]["obligaciones"]
    ) == 25

    resumen, _ = rel.resumir_obligaciones(
        contexto["postgresql"]["obligaciones"]
    )

    assert (
        resumen["deudas_propias_saldadas"]
        == 25
    )


def test_b1_reservas_compartidas(monkeypatch):

    llamadas = []

    def aportes(db, uid):
        llamadas.append(uid)

        return [{
            "id_meta": 8,
            "id_cuenta": 2,
            "nombre_meta": "Meta prueba",
            "nombre_cuenta": "Cuenta prueba",
            "tipo": "RESERVA",
            "monto": Decimal("30000.00"),
        }]

    monkeypatch.setattr(
        rag,
        "obtener_aportes_vinculados",
        aportes,
    )

    monkeypatch.setattr(
        rag,
        "obtener_cuentas_con_saldo",
        lambda db, uid: [{
            "id_cuenta": 2,
            "nombre_cuenta": "Cuenta prueba",
            "tipo_cuenta": "AHORROS",
            "saldo_actual": Decimal("80000.00"),
            "estado": "ACTIVA",
        }],
    )

    monkeypatch.setattr(
        rag,
        "consultar_planificacion",
        lambda *args, **kwargs: {
            "metas": []
        },
    )

    monkeypatch.setattr(
        rag,
        "_datos_sparql",
        semantica_simulada,
    )

    monkeypatch.setattr(
        rel,
        "_filas_reservas_usuario",
        no_llamar,
    )

    monkeypatch.setattr(
        rel,
        "_consultar_reservas_rdf",
        lambda uid: {
            (8, 2): Decimal("30000.00")
        },
    )

    contexto = rag.construir_contexto_rag(
        None,
        7,
        "Cuánto tengo reservado en mis metas",
    )

    resultado = rel.enriquecer_contexto_276(
        None,
        7,
        contexto,
    )

    assert llamadas == [7]

    assert (
        resultado["analisis_financiero"]
        ["cuentas"]["saldo_libre_total"]
        == "50000.00"
    )

    assert (
        resultado["analisis_financiero"]
        ["reservas"]["total_reservado_vinculado"]
        == "30000.00"
    )

    assert (
        resultado["fuseki"]["comprobaciones"]
        ["reservas_meta_cuenta"]
        ["coincide_con_postgresql"]
        is True
    )


def test_b1_sparql_no_consulta_categorias_innecesarias():

    consultas = []

    def ejecutar(consulta):
        consultas.append(consulta)

        return [{
            "fecha": {
                "value": "2026-11-24T10:00:00Z"
            }
        }]

    resultado = obtener_contexto_semantico_basico(
        7,
        incluir_categorias=False,
        ejecutar=ejecutar,
    )

    assert len(consultas) == 1

    assert resultado["categorias_semanticas"] == []

    assert (
        resultado["categorias_consultadas"]
        is False
    )


def test_b1_sparql_recupera_categorias_si_solicitan():

    consultas = []

    def ejecutar(consulta):

        consultas.append(consulta)

        if "SELECT ?fecha" in consulta:
            return [{
                "fecha": {
                    "value": "2026-11-24T10:00:00Z"
                }
            }]

        return [{
            "nombre": {
                "value": "Alimentación"
            },

            "clase": {
                "value": str(rel.FIN.CategoriaGasto)
            },
        }]

    resultado = obtener_contexto_semantico_basico(
        7,
        incluir_categorias=True,
        ejecutar=ejecutar,
    )

    assert len(consultas) == 2

    assert (
        resultado["categorias_semanticas"][0]
        ["clase_ontologica"]
        == "CategoriaGasto"
    )
