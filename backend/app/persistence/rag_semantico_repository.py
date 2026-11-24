
"""Consultas SPARQL fijas del RAG.

Capa Persistence.

No acepta SPARQL ni grafos procedentes de la PWA.
Construye consultas para el grafo del usuario autenticado.
"""

import re

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Callable

from rdflib import Namespace


FIN = Namespace(
    "http://www.semanticweb.org/user/"
    "ontologies/2026/8/untitled-ontology-20/"
)

OP = Namespace(
    "https://datos.finanzas.local/vocab/"
)

BASE_RECURSOS = (
    "https://datos.finanzas.local/usuario/"
)


class EvidenciaSemanticaInvalida(ValueError):
    """La respuesta RDF no cumple el contrato semántico."""


def _grafo(id_usuario: int) -> str:
    if type(id_usuario) is not int or id_usuario <= 0:
        raise ValueError("ID de usuario inválido")

    return (
        f"urn:finanzas:grafo:usuario:{id_usuario}"
    )


def _identificador_recurso(
    valor: str,
    id_usuario: int,
    tipo: str,
) -> int:
    prefijo = (
        f"{BASE_RECURSOS}"
        f"{id_usuario}/{tipo}/"
    )

    if (
        not isinstance(valor, str)
        or not valor.startswith(prefijo)
    ):
        raise EvidenciaSemanticaInvalida(
            "IRI RDF fuera del usuario autenticado"
        )

    sufijo = valor[len(prefijo):]

    if not re.fullmatch(
        r"[1-9][0-9]*",
        sufijo,
    ):
        raise EvidenciaSemanticaInvalida(
            "Identificador RDF inválido"
        )

    return int(sufijo)


def contar_obligaciones_rdf(
    id_usuario: int,
    ejecutar: Callable[
        [str], list[dict]
    ],
) -> dict[tuple[str, str], int]:
    """Cuenta obligaciones por tipo y estado dentro del grafo."""

    grafo = _grafo(id_usuario)

    consulta = f"""
        PREFIX fin: <{FIN}>
        PREFIX op: <{OP}>

        SELECT ?clase ?estado
               (COUNT(DISTINCT ?obligacion) AS ?cantidad)
        WHERE {{
            GRAPH <{grafo}> {{
                VALUES ?clase {{
                    fin:ObligacionPorPagar
                    fin:ObligacionPorCobrar
                }}

                ?obligacion a ?clase ;
                            op:estado ?estado .
            }}
        }}
        GROUP BY ?clase ?estado
    """

    conteos = defaultdict(int)

    for fila in ejecutar(consulta):
        try:
            clase = fila["clase"]["value"]
            estado = fila["estado"]["value"]
            cantidad = int(
                fila["cantidad"]["value"]
            )

        except (
            KeyError,
            ValueError,
            TypeError,
        ) as error:
            raise EvidenciaSemanticaInvalida(
                "Conteo RDF inválido"
            ) from error

        tipo = {
            str(FIN.ObligacionPorPagar):
                "POR_PAGAR",

            str(FIN.ObligacionPorCobrar):
                "POR_COBRAR",
        }.get(clase)

        if (
            tipo is None
            or estado not in {
                "ACTIVA",
                "SALDADA",
                "INACTIVA",
            }
            or cantidad < 0
        ):
            raise EvidenciaSemanticaInvalida(
                "Clasificación RDF inesperada"
            )

        conteos[(tipo, estado)] += cantidad

    return dict(conteos)


def reservas_netas_rdf(
    id_usuario: int,
    ejecutar: Callable[
        [str], list[dict]
    ],
) -> dict[tuple[int, int], Decimal]:
    """Consulta reservas netas por pareja meta-cuenta."""

    grafo = _grafo(id_usuario)

    consulta = f"""
        PREFIX fin: <{FIN}>

        SELECT ?meta ?cuenta
               (
                   SUM(
                       IF(
                           ?clase = fin:ReservaMeta,
                           ?monto,
                           -?monto
                       )
                   ) AS ?neto
               )
        WHERE {{
            GRAPH <{grafo}> {{
                VALUES ?clase {{
                    fin:ReservaMeta
                    fin:LiberacionMeta
                }}

                ?evento a ?clase ;
                    fin:correspondeAMeta ?meta ;
                    fin:seRealizaDesdeCuenta ?cuenta ;
                    fin:tieneMontoAporte ?monto ;
                    fin:tieneEstadoAporte "ACTIVO" .
            }}
        }}
        GROUP BY ?meta ?cuenta
    """

    pares = {}

    for fila in ejecutar(consulta):
        try:
            meta = _identificador_recurso(
                fila["meta"]["value"],
                id_usuario,
                "meta",
            )

            cuenta = _identificador_recurso(
                fila["cuenta"]["value"],
                id_usuario,
                "cuenta",
            )

            neto = Decimal(
                fila["neto"]["value"]
            )

        except (
            KeyError,
            InvalidOperation,
            ValueError,
            TypeError,
        ) as error:
            raise EvidenciaSemanticaInvalida(
                "Resultado RDF inválido"
            ) from error

        if not neto.is_finite():
            raise EvidenciaSemanticaInvalida(
                "Monto RDF no finito"
            )

        clave = (meta, cuenta)

        if clave in pares:
            raise EvidenciaSemanticaInvalida(
                "Agrupación RDF duplicada"
            )

        pares[clave] = neto

    return pares
