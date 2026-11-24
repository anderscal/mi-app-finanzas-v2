
"""Paso 27.6.1: pruebas SQL/SPARQL sin servicios externos.

Verifica cálculos monetarios, integridad financiera,
aislamiento de usuarios y consistencia PostgreSQL/Fuseki.
"""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.business import rag_relaciones_276 as rel
from app.routers import rag_router


OBLIGACIONES = [
    {
        "tipo_obligacion": "POR_PAGAR",
        "estado": "SALDADA",
        "monto_pendiente": Decimal("0"),
    },
    {
        "tipo_obligacion": "POR_COBRAR",
        "estado": "SALDADA",
        "monto_pendiente": Decimal("0"),
    },
    {
        "tipo_obligacion": "POR_PAGAR",
        "estado": "SALDADA",
        "monto_pendiente": Decimal("0"),
    },
    {
        "tipo_obligacion": "POR_COBRAR",
        "estado": "SALDADA",
        "monto_pendiente": Decimal("0"),
    },
    {
        "tipo_obligacion": "POR_COBRAR",
        "estado": "ACTIVA",
        "monto_pendiente": Decimal("50000"),
    },
    {
        "tipo_obligacion": "POR_COBRAR",
        "estado": "ACTIVA",
        "monto_pendiente": Decimal("10000"),
    },
    {
        "tipo_obligacion": "POR_COBRAR",
        "estado": "SALDADA",
        "monto_pendiente": Decimal("0"),
    },
    {
        "tipo_obligacion": "POR_PAGAR",
        "estado": "SALDADA",
        "monto_pendiente": Decimal("0"),
    },
    {
        "tipo_obligacion": "POR_PAGAR",
        "estado": "ACTIVA",
        "monto_pendiente": Decimal("50000"),
    },
    {
        "tipo_obligacion": "POR_COBRAR",
        "estado": "ACTIVA",
        "monto_pendiente": Decimal("30000"),
    },
    {
        "tipo_obligacion": "POR_PAGAR",
        "estado": "ACTIVA",
        "monto_pendiente": Decimal("50000"),
    },
]


def f(tipo, monto, meta=1, cuenta=2):
    return {
        "id_meta": meta,
        "id_cuenta": cuenta,
        "tipo": tipo,
        "monto": Decimal(monto),
        "nombre_meta": "Meta personal de prueba",
        "nombre_cuenta": "Cuenta de prueba",
    }


def test_276_deudas_totales_sin_truncar():
    datos, conteos = rel.resumir_obligaciones(
        OBLIGACIONES
    )

    assert datos["obligaciones_totales"] == 11
    assert datos["deudas_propias_saldadas"] == 3
    assert datos["cobros_saldados"] == 3
    assert datos["monto_pendiente_por_cobrar"] == "90000.00"
    assert datos["monto_pendiente_por_pagar"] == "100000.00"

    assert conteos[
        ("POR_PAGAR", "SALDADA")
    ] == 3


def test_276_no_trunca_veinticinco_obligaciones():
    filas = [
        dict(OBLIGACIONES[0])
        for _ in range(25)
    ]

    datos, _ = rel.resumir_obligaciones(
        filas
    )

    assert datos["deudas_propias_saldadas"] == 25


def test_276_rechaza_importe_inconsistente():
    filas = [
        dict(
            OBLIGACIONES[0],
            monto_pendiente=Decimal("10"),
        )
    ]

    with pytest.raises(
        HTTPException
    ) as error:
        rel.resumir_obligaciones(filas)

    assert error.value.status_code == 409


def test_276_reserva_menos_liberacion():
    datos, pares = rel.resumir_reservas([
        f("RESERVA", "50000"),
        f("LIBERACION", "20000"),
        f("RESERVA", "7000", meta=3),
    ])

    # Los importes monetarios deben conservar
    # sus dos posiciones decimales.
    assert (
        datos["total_reservado_vinculado"]
        == "37000.00"
    )

    assert datos["numero_metas_con_reserva"] == 2

    assert pares[(1, 2)] == Decimal("30000")


def test_276_rechaza_liberacion_excesiva():
    with pytest.raises(HTTPException):
        rel.resumir_reservas([
            f("LIBERACION", "20000")
        ])


def _binding(valor):
    return {"value": str(valor)}


def test_276_rdf_reservas_aisladas(monkeypatch):
    vistas = []

    def consultar(sparql):
        vistas.append(sparql)

        return [{
            "meta": _binding(
                "https://datos.finanzas.local/"
                "usuario/7/meta/1"
            ),
            "cuenta": _binding(
                "https://datos.finanzas.local/"
                "usuario/7/cuenta/2"
            ),
            "neto": _binding("30000.00"),
        }]

    monkeypatch.setattr(
        rel,
        "consultar_select",
        consultar,
    )

    netos = rel._consultar_reservas_rdf(7)

    assert netos[(1, 2)] == Decimal("30000.00")

    assert (
        "GRAPH <urn:finanzas:grafo:usuario:7>"
        in vistas[0]
    )

    assert "fin:correspondeAMeta" in vistas[0]


def test_276_rdf_rechaza_otro_usuario(monkeypatch):
    monkeypatch.setattr(
        rel,
        "consultar_select",
        lambda q: [{
            "meta": _binding(
                "https://datos.finanzas.local/"
                "usuario/8/meta/1"
            ),
            "cuenta": _binding(
                "https://datos.finanzas.local/"
                "usuario/7/cuenta/2"
            ),
            "neto": _binding("100"),
        }],
    )

    with pytest.raises(
        HTTPException
    ) as error:
        rel._consultar_reservas_rdf(7)

    assert error.value.status_code == 409


def _contexto(temas):
    return {
        "temas_recuperados": temas,
        "postgresql": {},
        "fuseki": {
            "fecha_instantanea": (
                "2026-11-23T15:00:00+00:00"
            ),
        },
        "limitaciones": [],
    }


def _simular_consultas(
    monkeypatch,
    reserva="30000.00",
    contar_deudas=True,
):
    consultas = []

    def consultar(sparql):
        consultas.append(sparql)

        if "COUNT(DISTINCT ?obligacion)" in sparql:
            if not contar_deudas:
                return []

            conteos = [
                ("ObligacionPorPagar", "SALDADA", 3),
                ("ObligacionPorCobrar", "SALDADA", 3),
                ("ObligacionPorPagar", "ACTIVA", 2),
                ("ObligacionPorCobrar", "ACTIVA", 3),
            ]

            return [
                {
                    "clase": _binding(
                        str(rel.FIN) + clase
                    ),
                    "estado": _binding(estado),
                    "cantidad": _binding(n),
                }
                for clase, estado, n in conteos
            ]

        return [{
            "meta": _binding(
                "https://datos.finanzas.local/"
                "usuario/7/meta/1"
            ),
            "cuenta": _binding(
                "https://datos.finanzas.local/"
                "usuario/7/cuenta/2"
            ),
            "neto": _binding(reserva),
        }]

    monkeypatch.setattr(
        rel,
        "consultar_select",
        consultar,
    )

    monkeypatch.setattr(
        rel,
        "consultar_planificacion",
        lambda db, uid: {
            "obligaciones": OBLIGACIONES,
        },
    )

    monkeypatch.setattr(
        rel,
        "_filas_reservas_usuario",
        lambda db, uid: [
            f("RESERVA", "50000"),
            f("LIBERACION", "20000"),
        ],
    )

    return consultas


def test_276_enriquece_sql_y_verifica_fuseki(
    monkeypatch,
):
    consultas = _simular_consultas(
        monkeypatch
    )

    resultado = rel.enriquecer_contexto_276(
        None,
        7,
        _contexto(["obligaciones", "metas"]),
    )

    assert (
        resultado["analisis_financiero"]
        ["obligaciones"]["deudas_propias_saldadas"]
        == 3
    )

    assert (
        resultado["analisis_financiero"]
        ["reservas"]["total_reservado_vinculado"]
        == "30000.00"
    )

    assert (
        resultado["fuseki"]["comprobaciones"]
        ["tipos_obligaciones"]
        ["coincide_con_postgresql"]
        is True
    )

    assert (
        resultado["fuseki"]["comprobaciones"]
        ["reservas_meta_cuenta"]
        ["coincide_con_postgresql"]
        is True
    )

    assert len(consultas) == 2

    assert all(
        "GRAPH <urn:finanzas:grafo:usuario:7>" in c
        for c in consultas
    )


def test_276_se_ve_divergencia_sin_sobrescribir_sql(
    monkeypatch,
):
    _simular_consultas(
        monkeypatch,
        reserva="99999.00",
    )

    resultado = rel.enriquecer_contexto_276(
        None,
        7,
        _contexto(["metas"]),
    )

    # El importe de PostgreSQL no debe cambiar
    # por una discrepancia semántica.
    assert (
        resultado["analisis_financiero"]
        ["reservas"]["total_reservado_vinculado"]
        == "30000.00"
    )

    assert (
        resultado["fuseki"]["comprobaciones"]
        ["reservas_meta_cuenta"]
        ["coincide_con_postgresql"]
        is False
    )

    assert any(
        "Discrepancia semántica" in x
        for x in resultado["limitaciones"]
    )


def test_276_no_consulta_deudas_si_solo_solicitan_cuentas(
    monkeypatch,
):
    def fallar(*args, **kwargs):
        raise AssertionError(
            "No debe consultar relaciones extras"
        )

    monkeypatch.setattr(
        rel,
        "consultar_select",
        fallar,
    )

    resultado = _contexto(["cuentas"])

    assert (
        rel.enriquecer_contexto_276(
            None,
            7,
            resultado,
        )
        is resultado
    )


def test_276_router_conserva_flujo_rag(
    monkeypatch,
):
    eventos = []

    monkeypatch.setattr(
        rag_router,
        "asegurar_actualizacion_para_rag",
        lambda db, uid: eventos.append(
            "sincronizacion"
        ),
    )

    monkeypatch.setattr(
        rag_router,
        "construir_contexto_rag",
        lambda db, uid, p: _contexto(
            ["obligaciones"]
        ),
    )

    monkeypatch.setattr(
        rag_router,
        "enriquecer_contexto_276",
        lambda db, uid, ctx: (
            eventos.append("enriquecimiento")
            or ctx
        ),
    )

    resultado = rag_router._recuperar(
        None,
        7,
        "Cuántas deudas tengo",
    )

    assert eventos == [
        "sincronizacion",
        "enriquecimiento",
    ]

    assert resultado["fuseki"]["vigencia"] in (
        "RECIENTE",
        "ANTIGUA",
    )
