import argparse
import base64
import json
import os
import time

from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlencode

from rdflib import Graph


HOST = "127.0.0.1"
PORT = 3031

DATASET = "/finanzas_demo"

TTL = (
    Path(__file__).resolve().parent.parent
    / "ontologia"
    / "modeloConceptualFinal_v2.ttl"
)

GRAFO = "urn:finanzas:qa:railway:285c2"

GRAFO_DENEGADO = GRAFO + ":denegado"

PREFIJO = (
    "PREFIX : "
    "<http://www.semanticweb.org/user/"
    "ontologies/2026/8/untitled-ontology-20/>"
)

PASSWORD = os.getenv("QA_FUSEKI_PASSWORD", "")


def comprobar(condicion, mensaje):

    if not condicion:
        raise RuntimeError(mensaje)


def solicitud(
    metodo,
    ruta,
    cuerpo=None,
    tipo=None,
    auth="correcta",
):

    headers = {
        "Accept": "application/sparql-results+json"
    }

    if tipo:
        headers["Content-Type"] = tipo

    if auth is not None:

        password = (
            PASSWORD
            if auth == "correcta"
            else "password-incorrecta"
        )

        credencial = base64.b64encode(
            f"fp_backend:{password}".encode("ascii")
        ).decode("ascii")

        headers["Authorization"] = (
            "Basic " + credencial
        )

    conexion = HTTPConnection(
        HOST,
        PORT,
        timeout=12,
    )

    try:

        conexion.request(
            metodo,
            DATASET + ruta,
            body=cuerpo,
            headers=headers,
        )

        respuesta = conexion.getresponse()

        return (
            respuesta.status,
            respuesta.read(),
        )

    finally:

        conexion.close()


def consulta(query, auth="correcta"):

    return solicitud(

        "POST",

        "/sparql",

        urlencode({
            "query": query
        }).encode("utf-8"),

        "application/x-www-form-urlencoded",

        auth,
    )


def datos_query(query):

    estado, cuerpo = consulta(query)

    comprobar(
        estado == 200,
        f"Consulta rechazada: HTTP {estado}",
    )

    return json.loads(cuerpo.decode("utf-8"))


def contar_triples():

    resultado = datos_query(
        "SELECT (COUNT(*) AS ?total) "
        "WHERE { ?s ?p ?o }"
    )

    return int(
        resultado["results"]["bindings"][0]
        ["total"]["value"]
    )


def contiene_demo():

    return datos_query(
        PREFIJO
        + """
        ASK {
            :usuarioDemo a :Usuario .
            :reservaViaje001 a :ReservaMeta .
        }
        """
    )["boolean"] is True


def contiene_marcador(grafo):

    return datos_query(
        f"ASK {{ GRAPH <{grafo}> "
        "{ ?s ?p ?o } }"
    )["boolean"] is True


def ruta_grafo(grafo):

    return "/data?" + urlencode({
        "graph": grafo
    })


def esperar():

    for _ in range(60):

        try:

            estado, _ = consulta(
                "SELECT * WHERE {}"
            )

        except OSError:

            time.sleep(1)

            continue

        if estado == 200:

            print("SERVIDOR: DISPONIBLE")

            return

        if estado in (401, 403):

            raise RuntimeError(
                "Credenciales QA rechazadas."
            )

        time.sleep(1)

    raise RuntimeError(
        "Fuseki QA no disponible."
    )


def verificar_seguridad():

    query = "SELECT * WHERE { ?s ?p ?o } LIMIT 1"

    ttl = b'<urn:qa:s> <urn:qa:p> "QA" .'

    for auth in (None, "incorrecta"):

        estado, _ = consulta(
            query,
            auth=auth,
        )

        comprobar(
            estado in (401, 403),
            f"Consulta insegura: HTTP {estado}",
        )

        estado, _ = solicitud(

            "GET",

            "/data?default",

            auth=auth,
        )

        comprobar(
            estado in (401, 403),
            f"Lectura RDF insegura: HTTP {estado}",
        )

        for metodo in ("POST", "PUT"):

            estado, _ = solicitud(

                metodo,

                ruta_grafo(GRAFO_DENEGADO),

                ttl,

                "text/turtle",

                auth,
            )

            comprobar(
                estado in (401, 403),
                f"Escritura insegura: HTTP {estado}",
            )

    comprobar(
        not contiene_marcador(GRAFO_DENEGADO),
        "Se encontraron triples no autorizados.",
    )

    print("ACCESO SIN CREDENCIALES: BLOQUEADO")

    print("CREDENCIALES INCORRECTAS: BLOQUEADAS")


    # SPARQL Update no debe estar habilitado.

    update = (
        f"INSERT DATA {{ GRAPH <{GRAFO_DENEGADO}> "
        '{ <urn:qa:s> <urn:qa:p> "QA" } }'
    )

    for endpoint in ("/update", "/sparql"):

        estado, _ = solicitud(

            "POST",

            endpoint,

            urlencode({
                "update": update
            }).encode("utf-8"),

            "application/x-www-form-urlencoded",
        )

        comprobar(
            estado in (400, 403, 404, 405, 415),
            f"SPARQL Update inesperado: HTTP {estado}",
        )

    comprobar(
        not contiene_marcador(GRAFO_DENEGADO),
        "SPARQL Update modifico el dataset.",
    )

    print("SPARQL UPDATE: NO HABILITADO")


def cargar_ontologia():

    grafo = Graph()

    grafo.parse(
        str(TTL),
        format="turtle",
    )

    comprobar(
        len(grafo) >= 354,
        "Ontologia incompleta.",
    )

    total = contar_triples()

    if total == 0:

        estado, _ = solicitud(

            "POST",

            "/data?default",

            TTL.read_bytes(),

            "text/turtle; charset=utf-8",
        )

        comprobar(
            200 <= estado < 300,
            f"Carga rechazada: HTTP {estado}",
        )

    comprobar(
        contar_triples() == len(grafo),
        "Cantidad de triples diferente al TTL.",
    )

    comprobar(
        contiene_demo(),
        "Individuos de demostracion no encontrados.",
    )

    print("ONTOLOGIA:", contar_triples(), "triples")


def crear_marcador():

    ttl = b'<urn:qa:s> <urn:qa:p> "persistencia" .'

    estado, _ = solicitud(

        "PUT",

        ruta_grafo(GRAFO),

        ttl,

        "text/turtle",
    )

    comprobar(
        200 <= estado < 300,
        f"Publicacion rechazada: HTTP {estado}",
    )

    comprobar(
        contiene_marcador(GRAFO),
        "Grafo de prueba no encontrado.",
    )

    print("PUBLICACION RDF AUTENTICADA: CORRECTA")


def verificar_reinicio():

    comprobar(
        contiene_marcador(GRAFO),
        "El marcador no sobrevivio al reinicio.",
    )

    comprobar(
        contiene_demo(),
        "La ontologia no sobrevivio al reinicio.",
    )

    print("PERSISTENCIA TDB2: APROBADA")

    estado, _ = solicitud(

        "DELETE",

        ruta_grafo(GRAFO),
    )

    comprobar(
        200 <= estado < 300,
        f"No se pudo retirar marcador: HTTP {estado}",
    )

    comprobar(
        not contiene_marcador(GRAFO),
        "El marcador temporal sigue presente.",
    )

    print("MARCADOR TEMPORAL RETIRADO")


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "fase",
        choices=["inicial", "reinicio"],
    )

    args = parser.parse_args()

    comprobar(
        len(PASSWORD) >= 32,
        "Configura QA_FUSEKI_PASSWORD.",
    )

    esperar()

    verificar_seguridad()

    cargar_ontologia()

    if args.fase == "inicial":

        crear_marcador()

    else:

        verificar_reinicio()

    for _ in range(20):

        comprobar(
            contar_triples() >= 354,
            "Consulta RDF inconsistente.",
        )

    print("CONSULTAS SUCESIVAS: 20/20")

    print("VALIDACION:", args.fase.upper(), "APROBADA")


if __name__ == "__main__":

    main()