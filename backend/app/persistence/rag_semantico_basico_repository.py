
"""Recuperación de metadatos y categorías semánticas.

Capa Persistence.
Consultas SPARQL fijas, restringidas al grafo
del usuario autenticado.
"""

from typing import Callable

from app.persistence.rag_semantico_repository import (
    FIN,
    OP,
    EvidenciaSemanticaInvalida,
)


def obtener_contexto_semantico_basico(
    id_usuario: int,
    incluir_categorias: bool,
    ejecutar: Callable,
) -> dict:

    if type(id_usuario) is not int or id_usuario <= 0:
        raise ValueError("Usuario inválido")

    grafo = f"urn:finanzas:grafo:usuario:{id_usuario}"

    consulta_fecha = f"""
        PREFIX fin: <{FIN}>
        PREFIX op: <{OP}>

        SELECT ?fecha
        WHERE {{
            GRAPH <{grafo}> {{
                ?usuario a fin:Usuario ;
                         op:exportadoEn ?fecha .
            }}
        }}
        LIMIT 1
    """

    fechas = ejecutar(consulta_fecha)

    if not fechas:
        raise EvidenciaSemanticaInvalida(
            "Todavía no existe una instantánea RDF "
            "para este usuario."
        )

    try:
        fecha = fechas[0]["fecha"]["value"]
    except (KeyError, TypeError, IndexError) as error:
        raise EvidenciaSemanticaInvalida(
            "Fecha de instantánea RDF inválida"
        ) from error

    categorias = []

    if incluir_categorias:

        consulta_categorias = f"""
            PREFIX fin: <{FIN}>

            SELECT DISTINCT ?nombre ?clase
            WHERE {{
                GRAPH <{grafo}> {{
                    VALUES ?clase {{
                        fin:CategoriaGasto
                        fin:CategoriaIngreso
                    }}

                    ?categoria a ?clase ;
                        fin:tieneNombreCategoria ?nombre .
                }}
            }}
            ORDER BY ?nombre ?clase
        """

        for fila in ejecutar(consulta_categorias):
            nombre = fila.get(
                "nombre", {}
            ).get("value")

            clase = fila.get(
                "clase", {}
            ).get("value", "")

            if nombre:
                categorias.append({
                    "nombre": nombre,
                    "clase_ontologica": clase.rsplit(
                        "/", 1
                    )[-1],
                })

    return {
        "grafo": grafo,
        "fecha_instantanea": fecha,
        "categorias_consultadas": incluir_categorias,
        "categorias_semanticas": categorias,
        "advertencia": (
            "Fuseki contiene una instantánea "
            "del conocimiento financiero. "
            "Sus tipos ontológicos no equivalen "
            "automáticamente a clasificaciones "
            "como discrecional o necesario."
        ),
    }
