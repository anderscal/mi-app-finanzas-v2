"""Consultas SPARQL de la proyeccion financiera."""

from app.persistence.fuseki_client import (
    consultar_select,
)

from app.persistence.rag_semantico_repository import (
    FIN,
    OP,
    _grafo,
)


def obtener_filas_cuentas(
    id_usuario,
):

    grafo = _grafo(
        id_usuario
    )

    return consultar_select(
        f'''
        PREFIX fin: <{FIN}>
        PREFIX op: <{OP}>

        SELECT
            ?id
            ?nombre
            ?real
            ?reservado
            ?libre

        WHERE {{

            GRAPH <{grafo}> {{

                ?cuenta a fin:CuentaFinanciera ;

                    op:idCuenta ?id ;

                    fin:tieneNombreCuenta ?nombre ;

                    fin:tieneSaldoReal ?real ;

                    fin:tieneMontoReservado ?reservado ;

                    fin:tieneSaldoLibre ?libre .

            }}

        }}

        ORDER BY ?id
        '''
    )