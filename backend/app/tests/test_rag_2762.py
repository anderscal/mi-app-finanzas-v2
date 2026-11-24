
"""Pruebas de separación Business / Persistence del RAG."""

from decimal import Decimal

import pytest

from app.business import (
    rag_relaciones_276 as rel,
)

from app.persistence import (
    rag_financiero_repository as sqlrepo,
)

from app.persistence import (
    rag_semantico_repository as semrepo,
)


def _binding(valor):
    return {"value": str(valor)}


def test_2762_consulta_obligaciones_aislada():
    consultas = []

    def consultar(query):
        consultas.append(query)

        return [{
            "clase": _binding(
                str(semrepo.FIN.ObligacionPorPagar)
            ),
            "estado": _binding("SALDADA"),
            "cantidad": _binding(3),
        }]

    resultado = semrepo.contar_obligaciones_rdf(
        7,
        consultar,
    )

    assert resultado == {
        ("POR_PAGAR", "SALDADA"): 3
    }

    assert (
        "GRAPH <urn:finanzas:grafo:usuario:7>"
        in consultas[0]
    )

    assert "VALUES ?clase" in consultas[0]


def test_2762_consulta_reservas_aislada():
    consultas = []

    def consultar(query):
        consultas.append(query)

        return [{
            "meta": _binding(
                "https://datos.finanzas.local/"
                "usuario/7/meta/4"
            ),
            "cuenta": _binding(
                "https://datos.finanzas.local/"
                "usuario/7/cuenta/2"
            ),
            "neto": _binding("12000.00"),
        }]

    resultado = semrepo.reservas_netas_rdf(
        7,
        consultar,
    )

    assert resultado[
        (4, 2)
    ] == Decimal("12000.00")

    assert (
        "GRAPH <urn:finanzas:grafo:usuario:7>"
        in consultas[0]
    )


def test_2762_rechaza_iri_de_otro_usuario():

    def consultar(_):
        return [{
            "meta": _binding(
                "https://datos.finanzas.local/"
                "usuario/8/meta/4"
            ),
            "cuenta": _binding(
                "https://datos.finanzas.local/"
                "usuario/7/cuenta/2"
            ),
            "neto": _binding("12000.00"),
        }]

    with pytest.raises(
        semrepo.EvidenciaSemanticaInvalida
    ):
        semrepo.reservas_netas_rdf(
            7,
            consultar,
        )


def test_2762_consulta_solo_temas_relevantes(
    monkeypatch,
):
    llamadas = []

    monkeypatch.setattr(
        rel,
        "consultar_planificacion",
        lambda db, id_usuario: {
            "obligaciones": [{
                "tipo_obligacion": "POR_PAGAR",
                "estado": "SALDADA",
                "monto_pendiente": Decimal("0.00"),
            }],
        },
    )

    monkeypatch.setattr(
        rel,
        "_consultar_tipos_obligacion_rdf",
        lambda uid: (
            llamadas.append("obligaciones")
            or {("POR_PAGAR", "SALDADA"): 1}
        ),
    )

    monkeypatch.setattr(
        rel,
        "_consultar_reservas_rdf",
        lambda uid: (
            llamadas.append("reservas")
            or {}
        ),
    )

    contexto = {
        "temas_recuperados": [
            "obligaciones"
        ],
        "fuseki": {},
        "limitaciones": [],
    }

    rel.enriquecer_contexto_276(
        None,
        7,
        contexto,
    )

    assert llamadas == [
        "obligaciones"
    ]

    assert (
        contexto["fuseki"]["comprobaciones"]
        ["tipos_obligaciones"]
        ["coincide_con_postgresql"]
        is True
    )


def test_2762_repositorio_sql_exige_id_usuario_valido():

    for valor in (
        0,
        -1,
        "7",
        True,
    ):
        with pytest.raises(ValueError):
            sqlrepo.obtener_aportes_vinculados(
                None,
                valor,
            )
