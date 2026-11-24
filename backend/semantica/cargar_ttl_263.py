
import json
import time

from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rdflib import Graph


BASE = Path(__file__).resolve().parent

TTL = (
    BASE
    / "ontologia"
    / "modeloConceptualFinal_v2.ttl"
)

SERVIDOR = "http://127.0.0.1:3030"
DATASET = "/finanzas_demo"

URL_CONSULTA = (
    SERVIDOR
    + DATASET
    + "/sparql"
)

URL_CARGA = (
    SERVIDOR
    + DATASET
    + "/data?default"
)

PREFIX = (
    "PREFIX : "
    "<http://www.semanticweb.org/user/"
    "ontologies/2026/8/untitled-ontology-20/>"
)


def consultar_sparql(consulta: str) -> dict:
    cuerpo = urlencode({
        "query": consulta
    }).encode("utf-8")

    solicitud = Request(
        URL_CONSULTA,
        data=cuerpo,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded",
            "Accept":
                "application/sparql-results+json",
        },
        method="POST",
    )

    with urlopen(
        solicitud,
        timeout=15
    ) as respuesta:
        return json.loads(
            respuesta.read().decode("utf-8")
        )


def consultar_cantidad() -> int:
    respuesta = consultar_sparql(
        """
        SELECT (COUNT(*) AS ?total)
        WHERE {
            ?s ?p ?o .
        }
        """
    )

    filas = respuesta[
        "results"
    ]["bindings"]

    return int(
        filas[0]["total"]["value"]
    )


def contiene_ontologia() -> bool:
    consulta = (
        PREFIX
        + """
        ASK {
            :usuarioDemo a :Usuario .
            :reservaViaje001 a :ReservaMeta .
        }
        """
    )

    respuesta = consultar_sparql(
        consulta
    )

    return respuesta.get(
        "boolean",
        False
    ) is True


def esperar_servidor() -> None:
    ultimo_error = None

    for _ in range(40):
        try:
            consultar_cantidad()
            return

        except (
            HTTPError,
            URLError,
            TimeoutError,
            ConnectionError,
            OSError
        ) as error:
            ultimo_error = error
            time.sleep(1)

    raise RuntimeError(
        "No se pudo conectar con Fuseki "
        f"en {URL_CONSULTA}. "
        "Comprueba que Docker Desktop esté "
        "iniciado y el contenedor esté activo. "
        f"Último error: {ultimo_error}"
    )


def cargar_ontologia():
    if not TTL.is_file():
        raise FileNotFoundError(
            f"No se encontró el TTL: {TTL}"
        )

    # Validamos el archivo antes de enviarlo.
    grafo = Graph()
    grafo.parse(
        TTL,
        format="turtle"
    )

    cantidad_archivo = len(grafo)

    if cantidad_archivo < 354:
        raise RuntimeError(
            "El TTL tiene menos triples de "
            "los esperados para el modelo "
            "final validado en 26.2. "
            f"Se encontraron {cantidad_archivo}."
        )

    print(
        "TTL validado localmente:",
        cantidad_archivo,
        "triples"
    )

    esperar_servidor()

    existentes = consultar_cantidad()

    # No sobrescribir jamás un dataset
    # que ya tiene contenido.
    if existentes > 0:
        if (
            existentes < cantidad_archivo
            or not contiene_ontologia()
        ):
            raise RuntimeError(
                "El dataset no está vacío, "
                "pero no coincide con la "
                "ontología esperada. "
                "No se modificó ningún dato. "
                "Revisa el contenido de Fuseki."
            )

        print(
            "El dataset ya contiene la "
            "ontología. No se vuelve a cargar."
        )

        print(
            "Triples existentes:",
            existentes
        )

        return

    # Primera carga:
    # POST añade triples al grafo por defecto.
    contenido = TTL.read_bytes()

    solicitud = Request(
        URL_CARGA,
        data=contenido,
        headers={
            "Content-Type":
                "text/turtle; charset=utf-8",
        },
        method="POST",
    )

    try:
        with urlopen(
            solicitud,
            timeout=60
        ) as respuesta:
            respuesta.read()

    except HTTPError as error:
        detalle = error.read(
            1000
        ).decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"Fuseki rechazó la carga: "
            f"HTTP {error.code}. {detalle}"
        ) from error

    cargados = consultar_cantidad()

    if cargados != cantidad_archivo:
        raise RuntimeError(
            "El número de triples después "
            "de la carga no coincide. "
            f"TTL: {cantidad_archivo}; "
            f"Fuseki: {cargados}."
        )

    if not contiene_ontologia():
        raise RuntimeError(
            "Los triples se cargaron, "
            "pero faltan individuos esperados."
        )

    print(
        "Ontología cargada correctamente."
    )

    print(
        "Total en Fuseki:",
        cargados,
        "triples"
    )

    print(
        "Dataset persistente:",
        "finanzas_demo"
    )


if __name__ == "__main__":
    cargar_ontologia()
