"""Recuperación semántica dinámica. Persistence.

Construye SELECT SPARQL desde patrones autorizados.
No acepta SPARQL libre ni IRIs de usuario externas.
"""

from rdflib import Literal

from app.persistence.rag_semantico_repository import (
    FIN,
    OP,
    EvidenciaSemanticaInvalida,
)


PATRONES = {

    "rdf_reservas": (
        {
            "meta",
            "cuenta",
            "tipo",
            "estado",
            "fecha",
        },
        """
        VALUES ?clase {
            fin:ReservaMeta
            fin:LiberacionMeta
        }

        ?raiz a ?clase ;
            fin:correspondeAMeta ?recursoMeta ;
            fin:seRealizaDesdeCuenta ?recursoCuenta ;
            fin:tieneFechaOperacion ?fecha ;
            fin:tieneEstadoAporte ?estado .

        ?recursoMeta fin:tieneNombreMeta ?meta .
        ?recursoCuenta fin:tieneNombreCuenta ?cuenta .

        BIND(
            IF(
                ?clase = fin:ReservaMeta,
                "RESERVA",
                "LIBERACION"
            ) AS ?tipo
        )
        """,
    ),

    "rdf_movimientos": (
        {
            "cuenta",
            "categoria",
            "obligacion",
            "tipo",
            "origen",
            "estado",
            "fecha",
        },
        """
        ?raiz fin:perteneceACuenta ?recursoCuenta ;
            fin:tieneFecha ?fecha ;
            op:tipoMovimiento ?tipo ;
            op:origen ?origen ;
            op:estado ?estado .

        ?recursoCuenta fin:tieneNombreCuenta ?cuenta .

        OPTIONAL {
            ?raiz fin:perteneceACategoria ?recursoCategoria .
            ?recursoCategoria fin:tieneNombreCategoria ?categoria .
        }

        OPTIONAL {
            ?raiz fin:relacionadoConObligacion ?recursoObligacion .
            ?recursoObligacion fin:tieneNombreObligacion ?obligacion .
        }
        """,
    ),

    "rdf_transferencias": (
        {
            "cuenta_origen",
            "cuenta_destino",
            "estado",
        },
        """
        ?raiz a fin:Transferencia ;
            fin:tieneCuentaOrigen ?origen ;
            fin:tieneCuentaDestino ?destino ;
            op:estado ?estado .

        ?origen fin:tieneNombreCuenta ?cuenta_origen .
        ?destino fin:tieneNombreCuenta ?cuenta_destino .
        """,
    ),

    "rdf_categorias": (
        {
            "nombre",
            "clase",
            "estado",
        },
        """
        VALUES ?claseIRI {
            fin:CategoriaGasto
            fin:CategoriaIngreso
        }

        ?raiz a ?claseIRI ;
            fin:tieneNombreCategoria ?nombre ;
            op:estado ?estado .

        BIND(
            IF(
                ?claseIRI = fin:CategoriaGasto,
                "CategoriaGasto",
                "CategoriaIngreso"
            ) AS ?clase
        )
        """,
    ),

    "rdf_obligaciones": (
        {
            "nombre",
            "clase",
            "estado",
        },
        """
        VALUES ?claseIRI {
            fin:ObligacionPorPagar
            fin:ObligacionPorCobrar
        }

        ?raiz a ?claseIRI ;
            fin:tieneNombreObligacion ?nombre ;
            op:estado ?estado .

        BIND(
            IF(
                ?claseIRI = fin:ObligacionPorPagar,
                "ObligacionPorPagar",
                "ObligacionPorCobrar"
            ) AS ?clase
        )
        """,
    ),

    "rdf_presupuestos": (
        {
            "categoria",
            "anio",
            "mes",
        },
        """
        ?raiz a fin:Presupuesto ;
            fin:aplicaACategoria ?recursoCategoria ;
            op:anio ?anio ;
            op:mes ?mes .

        ?recursoCategoria fin:tieneNombreCategoria ?categoria .
        """,
    ),
}


def _variable(nombre, disponibles):

    if nombre not in disponibles:
        raise ValueError(
            "Variable semántica no autorizada"
        )

    return "?" + nombre


def _filtro(filtro, disponibles):

    variable = _variable(
        filtro["campo"],
        disponibles,
    )

    operador = filtro["operador"]

    if operador == "es_nulo":
        return f"FILTER(!BOUND({variable}))"

    if operador == "no_nulo":
        return f"FILTER(BOUND({variable}))"

    valor = filtro["valor"]

    # RDFLib serializa el literal de manera segura.
    # Nunca se concatena SPARQL libre del usuario.

    literal = Literal(valor).n3()

    izquierda = variable
    derecha = literal

    if isinstance(valor, str):

        izquierda = f"LCASE(STR({variable}))"
        derecha = f"LCASE(STR({literal}))"

    if operador == "contiene":

        if not isinstance(valor, str):
            raise ValueError("Filtro textual inválido")

        return (
            f"FILTER(CONTAINS("
            f"{izquierda}, {derecha}))"
        )

    operadores = {
        "igual": "=",
        "distinto": "!=",
        "mayor": ">",
        "menor": "<",
        "mayor_igual": ">=",
        "menor_igual": "<=",
    }

    simbolo = operadores.get(operador)

    if simbolo is None:
        raise ValueError("Operador no autorizado")

    return (
        f"FILTER({izquierda} "
        f"{simbolo} {derecha})"
    )


def construir_sparql(usuario, plan):

    if type(usuario) is not int or usuario <= 0:
        raise ValueError("Usuario inválido")

    configuracion = PATRONES.get(
        plan["entidad"]
    )

    if configuracion is None:
        raise ValueError(
            "Patrón semántico no autorizado"
        )

    disponibles, patron = configuracion

    filtros = "\n".join(
        _filtro(filtro, disponibles)
        for filtro in plan["filtros"]
    )

    grafo = (
        f"urn:finanzas:grafo:usuario:{usuario}"
    )

    operacion = plan["operacion"]

    grupos = [
        _variable(nombre, disponibles)
        for nombre in plan["agrupar_por"]
    ]

    if operacion == "listar":

        campos = [
            _variable(nombre, disponibles)
            for nombre in plan["campos"]
        ]

        if not campos:
            raise ValueError("Listado sin variables")

        proyeccion = " ".join(campos)

        ordenables = disponibles

    elif operacion == "contar":

        proyeccion = (
            " ".join(grupos)
            + " (COUNT(*) AS ?valor)"
            + " (COUNT(*) AS ?cantidad)"
        )

        ordenables = {
            *plan["agrupar_por"],
            "valor",
            "cantidad",
        }

    else:

        raise ValueError(
            "Operación semántica no autorizada"
        )

    consulta = f"""
        PREFIX fin: <{FIN}>
        PREFIX op: <{OP}>

        SELECT {proyeccion}
        WHERE {{
            GRAPH <{grafo}> {{
                {patron}

                {filtros}
            }}
        }}
    """

    if operacion == "contar" and grupos:

        consulta += (
            "\nGROUP BY "
            + " ".join(grupos)
        )

    ordenes = []

    if plan["orden_campo"]:

        variable = _variable(
            plan["orden_campo"],
            ordenables,
        )

        direccion = (
            "DESC"
            if plan["descendente"]
            else "ASC"
        )

        ordenes.append(
            f"{direccion}({variable})"
        )

    if operacion == "listar":
        ordenes.append("ASC(?raiz)")

    elif grupos:
        ordenes.extend(grupos)

    if ordenes:

        consulta += (
            "\nORDER BY "
            + " ".join(ordenes)
        )

    limite = plan["limite"]

    if type(limite) is not int or not 1 <= limite <= 50:
        raise ValueError("Límite no autorizado")

    consulta += f"\nLIMIT {limite + 1}"

    return consulta


def ejecutar_consulta_rdf(usuario, plan, ejecutar):

    consulta = construir_sparql(
        usuario,
        plan,
    )

    resultado = ejecutar(consulta)

    limite = plan["limite"]

    if (
        not isinstance(resultado, list)
        or len(resultado) > limite + 1
    ):

        raise EvidenciaSemanticaInvalida(
            "Respuesta semántica inesperada"
        )

    if plan["operacion"] == "listar":

        campos = plan["campos"]

    else:

        campos = [
            *plan["agrupar_por"],
            "valor",
            "cantidad",
        ]

    filas = []

    for registro in resultado[:limite]:

        if not isinstance(registro, dict):
            raise EvidenciaSemanticaInvalida(
                "Fila RDF inválida"
            )

        fila = {}

        for campo in campos:

            dato = registro.get(campo)

            if dato is None:

                fila[campo] = None
                continue

            if (
                not isinstance(dato, dict)
                or dato.get("type") not in {
                    "literal",
                    "typed-literal",
                }
                or not isinstance(
                    dato.get("value"), str
                )
            ):

                raise EvidenciaSemanticaInvalida(
                    "Se esperaba un literal RDF"
                )

            valor = dato["value"]

            if campo in {
                "anio",
                "mes",
                "valor",
                "cantidad",
            }:

                try:
                    valor = int(valor)

                except ValueError as error:

                    raise EvidenciaSemanticaInvalida(
                        "Entero RDF inválido"
                    ) from error

            fila[campo] = valor

        filas.append(fila)

    return {
        "origen": "Fuseki/SPARQL",
        "entidad": plan["entidad"],
        "operacion": plan["operacion"],
        "filas": filas,
        "truncado": len(resultado) > limite,
        "limite": limite,
    }