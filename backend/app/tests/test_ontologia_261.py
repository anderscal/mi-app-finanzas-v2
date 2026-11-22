
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from rdflib import (
    Graph,
    Literal,
    Namespace,
    URIRef,
)

from rdflib.namespace import (
    OWL,
    RDF,
    RDFS,
    XSD,
)


# -------------------------------------
# UBICACIÓN DEL MODELO Y CONSULTAS
# -------------------------------------

BASE = (
    Path(__file__).resolve().parents[2]
    / "semantica"
)

TTL = (
    BASE
    / "ontologia"
    / "modeloConceptualFinal_v2.ttl"
)

CONSULTAS = BASE / "consultas"

IRI = (
    "http://www.semanticweb.org/user/"
    "ontologies/2026/8/"
    "untitled-ontology-20/"
)

F = Namespace(IRI)


# -------------------------------------
# CARGAR LA ONTOLOGÍA UNA SOLA VEZ
# -------------------------------------

@pytest.fixture(scope="module")
def grafo():
    assert TTL.is_file(), (
        f"Falta copiar el TTL final a: {TTL}"
    )

    g = Graph()

    g.parse(
        TTL,
        format="turtle"
    )

    return g


def consultar(grafo, nombre):
    archivo = CONSULTAS / nombre

    assert archivo.is_file(), (
        f"Falta la consulta SPARQL: {archivo}"
    )

    consulta = archivo.read_text(
        encoding="utf-8"
    )

    return list(
        grafo.query(consulta)
    )


# -------------------------------------
# PRUEBA 1: TURTLE E IDENTIFICADOR
# -------------------------------------

def test_261_turtle_valido_y_ontologia_identificada(
    grafo
):
    assert len(grafo) > 0

    assert (
        URIRef(IRI.rstrip("/")),
        RDF.type,
        OWL.Ontology
    ) in grafo


# -------------------------------------
# PRUEBA 2: CLASES Y HERENCIA
# -------------------------------------

def test_261_clases_originales_y_ampliacion(
    grafo
):
    clases = set(
        grafo.subjects(
            RDF.type,
            OWL.Class
        )
    )

    esperadas = {
        F.Usuario,
        F.CuentaFinanciera,
        F.CategoriaFinanciera,
        F.MovimientoFinanciero,
        F.Ingreso,
        F.Gasto,
        F.Transferencia,
        F.ObligacionFinanciera,
        F.Presupuesto,
        F.MetaFinanciera,
        F.AporteMeta,
        F.ReservaMeta,
        F.LiberacionMeta,
    }

    assert esperadas <= clases

    assert len(clases) >= 20

    assert (
        F.ReservaMeta,
        RDFS.subClassOf,
        F.AporteMeta
    ) in grafo

    assert (
        F.LiberacionMeta,
        RDFS.subClassOf,
        F.AporteMeta
    ) in grafo

    assert (
        F.ReservaMeta,
        OWL.disjointWith,
        F.LiberacionMeta
    ) in grafo

    assert (
        F.AporteMeta,
        OWL.disjointWith,
        F.MovimientoFinanciero
    ) in grafo


# -------------------------------------
# PRUEBA 3: PROPIEDADES Y DOMINIOS
# -------------------------------------

def test_261_propiedades_y_dominios(
    grafo
):
    objetos = {
        F.correspondeAMeta:
            F.MetaFinanciera,

        F.seRealizaDesdeCuenta:
            F.CuentaFinanciera,

        F.registradoPorUsuario:
            F.Usuario,
    }

    for propiedad, rango in objetos.items():
        assert (
            propiedad,
            RDF.type,
            OWL.ObjectProperty
        ) in grafo

        assert (
            propiedad,
            RDFS.domain,
            F.AporteMeta
        ) in grafo

        assert (
            propiedad,
            RDFS.range,
            rango
        ) in grafo

    datos = {
        F.tieneIdAporte:
            (F.AporteMeta, XSD.integer),

        F.tieneUUIDOperacion:
            (F.AporteMeta, XSD.string),

        F.tieneMontoAporte:
            (F.AporteMeta, XSD.decimal),

        # CORREGIDO:
        # El TTL final de Protégé utiliza
        # xsd:dateTime y no xsd:date.
        F.tieneFechaOperacion:
            (F.AporteMeta, XSD.dateTime),

        F.tieneEstadoAporte:
            (F.AporteMeta, XSD.string),

        F.tieneSaldoReal:
            (F.CuentaFinanciera, XSD.decimal),

        F.tieneMontoReservado:
            (F.CuentaFinanciera, XSD.decimal),

        F.tieneSaldoLibre:
            (F.CuentaFinanciera, XSD.decimal),

        F.tieneMontoVinculado:
            (F.MetaFinanciera, XSD.decimal),

        F.tieneMontoSinVincular:
            (F.MetaFinanciera, XSD.decimal),
    }

    for propiedad, (dominio, rango) in datos.items():
        assert (
            propiedad,
            RDF.type,
            OWL.DatatypeProperty
        ) in grafo

        assert (
            propiedad,
            RDFS.domain,
            dominio
        ) in grafo

        assert (
            propiedad,
            RDFS.range,
            rango
        ) in grafo


# -------------------------------------
# PRUEBA 4: CARDINALIDADES
# -------------------------------------

def test_261_cardinalidades_de_aporte(
    grafo
):
    relaciones = (
        (
            F.correspondeAMeta,
            F.MetaFinanciera
        ),
        (
            F.seRealizaDesdeCuenta,
            F.CuentaFinanciera
        ),
        (
            F.registradoPorUsuario,
            F.Usuario
        ),
    )

    for propiedad, clase in relaciones:
        restricciones = grafo.objects(
            F.AporteMeta,
            RDFS.subClassOf
        )

        assert any(
            (
                r,
                RDF.type,
                OWL.Restriction
            ) in grafo

            and (
                r,
                OWL.onProperty,
                propiedad
            ) in grafo

            and (
                r,
                OWL.onClass,
                clase
            ) in grafo

            and (
                r,
                OWL.qualifiedCardinality,
                Literal(
                    1,
                    datatype=XSD.nonNegativeInteger
                )
            ) in grafo

            for r in restricciones

        ), (
            "Falta cardinalidad exacta 1 "
            f"para {propiedad}"
        )


# -------------------------------------
# PRUEBA 5: INDIVIDUOS DE EJEMPLO
# -------------------------------------

def test_261_ejemplos_no_son_ingresos_ni_gastos(
    grafo
):
    eventos = (
        (
            F.reservaViaje001,
            F.ReservaMeta
        ),
        (
            F.liberacionViaje001,
            F.LiberacionMeta
        ),
    )

    identificadores = set()

    for individuo, clase in eventos:
        assert (
            individuo,
            RDF.type,
            OWL.NamedIndividual
        ) in grafo

        assert (
            individuo,
            RDF.type,
            clase
        ) in grafo

        assert (
            individuo,
            F.correspondeAMeta,
            F.metaViaje
        ) in grafo

        assert (
            individuo,
            F.seRealizaDesdeCuenta,
            F.cuentaNequi
        ) in grafo

        assert (
            individuo,
            F.registradoPorUsuario,
            F.usuarioDemo
        ) in grafo

        assert (
            individuo,
            RDF.type,
            F.Ingreso
        ) not in grafo

        assert (
            individuo,
            RDF.type,
            F.Gasto
        ) not in grafo

        uuid = list(
            grafo.objects(
                individuo,
                F.tieneUUIDOperacion
            )
        )

        assert len(uuid) == 1
        assert uuid[0].datatype == XSD.string

        identificador = UUID(
            str(uuid[0])
        )

        assert identificador not in identificadores

        identificadores.add(
            identificador
        )


# -------------------------------------
# PRUEBA 6: CLASIFICACIÓN DE GASTOS
# -------------------------------------

def test_261_consulta_clasificacion_de_gastos(
    grafo
):
    filas = consultar(
        grafo,
        "01_clasificacion_gastos.rq"
    )

    assert filas

    assert any(
        fila.categoria == F.restaurantes

        and fila.naturaleza == F.discrecional

        and str(fila.nombre) == "Restaurantes"

        for fila in filas
    )


# -------------------------------------
# PRUEBA 7: RESERVAS NETAS
# -------------------------------------

def test_261_consulta_reservas_netas(
    grafo
):
    filas = consultar(
        grafo,
        "02_reservas_netas.rq"
    )

    assert filas

    assert any(
        fila.meta == F.metaViaje

        and fila.cuenta == F.cuentaNequi

        and Decimal(
            str(fila.neto)
        ) == Decimal("400000.00")

        for fila in filas
    )


# -------------------------------------
# PRUEBA 8: SALDO REAL Y LIBRE
# -------------------------------------

def test_261_consulta_saldos_demostrativos(
    grafo
):
    filas = consultar(
        grafo,
        "03_saldos_demo.rq"
    )

    assert filas

    assert any(
        fila.cuenta == F.cuentaNequi
        for fila in filas
    )

    for fila in filas:
        real = Decimal(
            str(fila.real)
        )

        reservado = Decimal(
            str(fila.reservado)
        )

        libre = Decimal(
            str(fila.libre)
        )

        assert real - reservado == libre

    nequi = next(
        fila
        for fila in filas
        if fila.cuenta == F.cuentaNequi
    )

    assert Decimal(
        str(nequi.reservado)
    ) == Decimal("400000.00")


# -------------------------------------
# PRUEBA 9: COHERENCIA DE META
# -------------------------------------

def test_261_meta_demo_coincide_con_reserva_neta(
    grafo
):
    meta = F.metaViaje

    acumulados = list(
        grafo.objects(
            meta,
            F.tieneMontoAcumulado
        )
    )

    vinculados = list(
        grafo.objects(
            meta,
            F.tieneMontoVinculado
        )
    )

    antiguos = list(
        grafo.objects(
            meta,
            F.tieneMontoSinVincular
        )
    )

    assert (
        len(acumulados)
        == len(vinculados)
        == len(antiguos)
        == 1
    )

    acumulado = Decimal(
        str(acumulados[0])
    )

    vinculado = Decimal(
        str(vinculados[0])
    )

    antiguo = Decimal(
        str(antiguos[0])
    )

    assert acumulado == vinculado + antiguo

    assert vinculado == Decimal("400000.00")
