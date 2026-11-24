
import json
import shutil
import subprocess
import time

from pathlib import Path
from uuid import uuid4

import pytest

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.parse import urlencode

from urllib.request import (
    Request,
    urlopen,
)


# ---------------------------------------
# CONFIGURACIÓN
# ---------------------------------------

BASE = (
    Path(__file__).resolve().parents[2]
)

COMPOSE = (
    BASE
    / "semantica"
    / "docker"
    / "compose.yaml"
)

SERVIDOR = "http://127.0.0.1:3030"

DATASET = "/finanzas_demo"

ENDPOINT_CONSULTA = (
    SERVIDOR
    + DATASET
    + "/sparql"
)

ENDPOINT_UPDATE = (
    SERVIDOR
    + DATASET
    + "/update"
)

GRAFO_PRUEBAS = (
    "urn:finanzas:qa:tdb2"
)

PROPIEDAD_PRUEBAS = (
    "urn:finanzas:qa:estado"
)


# ---------------------------------------
# CONSULTAS SPARQL
# ---------------------------------------

def consultar(consulta: str) -> dict:
    cuerpo = urlencode({
        "query": consulta
    }).encode("utf-8")

    solicitud = Request(
        ENDPOINT_CONSULTA,
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
        timeout=10
    ) as respuesta:
        return json.loads(
            respuesta.read().decode("utf-8")
        )


def actualizar(consulta: str) -> None:
    solicitud = Request(
        ENDPOINT_UPDATE,
        data=consulta.encode("utf-8"),
        headers={
            "Content-Type":
                "application/sparql-update",
        },
        method="POST",
    )

    with urlopen(
        solicitud,
        timeout=15
    ) as respuesta:
        respuesta.read()


def contar_triples() -> int:
    resultado = consultar(
        """
        SELECT (COUNT(*) AS ?total)
        WHERE {
            ?s ?p ?o .
        }
        """
    )

    return int(
        resultado[
            "results"
        ]["bindings"][0]["total"]["value"]
    )


def marcador_existe(sujeto: str) -> bool:
    consulta = f"""
        ASK {{
            GRAPH <{GRAFO_PRUEBAS}> {{
                <{sujeto}>
                    <{PROPIEDAD_PRUEBAS}>
                    "persistente" .
            }}
        }}
    """

    resultado = consultar(
        consulta
    )

    return resultado.get(
        "boolean",
        False
    ) is True


# ---------------------------------------
# ESPERAR REINICIO DEL SERVIDOR
# ---------------------------------------

def esperar_fuseki(
    segundos: int = 90
) -> None:
    limite = time.monotonic() + segundos
    ultimo_error = None

    while time.monotonic() < limite:
        try:
            contar_triples()
            return

        except (
            HTTPError,
            URLError,
            TimeoutError,
            ConnectionError,
            OSError
        ) as error:
            ultimo_error = error
            time.sleep(2)

    pytest.fail(
        "Fuseki no volvió a responder "
        "después del reinicio de Docker. "
        f"Último error: {ultimo_error}"
    )


# ---------------------------------------
# PRUEBA 1:
# DATASET TDB2 OPERATIVO
# ---------------------------------------

def test_263_tdb2_contiene_ontologia():
    assert COMPOSE.is_file(), (
        f"No existe compose.yaml: {COMPOSE}"
    )

    try:
        total = contar_triples()

    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError
    ) as error:
        pytest.fail(
            "No se pudo consultar Fuseki. "
            "Verifica que el contenedor esté "
            "iniciado y el TTL haya sido cargado. "
            f"Error: {error}"
        )

    assert total >= 354

    resultado = consultar(
        """
        PREFIX : <http://www.semanticweb.org/user/ontologies/2026/8/untitled-ontology-20/>

        ASK {
            :usuarioDemo a :Usuario .
            :reservaViaje001 a :ReservaMeta .
        }
        """
    )

    assert resultado["boolean"] is True


# ---------------------------------------
# PRUEBA 2:
# LOS DATOS SOBREVIVEN AL REINICIO
# ---------------------------------------

def test_263_marcador_sobrevive_reinicio_docker():
    assert COMPOSE.is_file()

    if shutil.which("docker") is None:
        pytest.fail(
            "Docker no se encontró en PATH. "
            "Instala o inicia Docker Desktop."
        )

    identificador = uuid4().hex

    sujeto = (
        "urn:finanzas:qa:marca:"
        + identificador
    )

    triple = (
        f"<{sujeto}> "
        f"<{PROPIEDAD_PRUEBAS}> "
        '"persistente" .'
    )

    insertar = f"""
        INSERT DATA {{
            GRAPH <{GRAFO_PRUEBAS}> {{
                {triple}
            }}
        }}
    """

    eliminar = f"""
        DELETE DATA {{
            GRAPH <{GRAFO_PRUEBAS}> {{
                {triple}
            }}
        }}
    """

    insertado = False

    try:
        # Crear un triple de prueba sin
        # modificar la ontología académica.
        actualizar(insertar)
        insertado = True

        assert marcador_existe(sujeto)

        # Reiniciar únicamente Fuseki.
        # NO borrar ni recrear el volumen.
        comando = [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "restart",
            "fuseki",
        ]

        try:
            resultado = subprocess.run(
                comando,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

        except subprocess.TimeoutExpired:
            pytest.fail(
                "Docker tardó demasiado "
                "en reiniciar Fuseki."
            )

        if resultado.returncode != 0:
            pytest.fail(
                "Docker no pudo reiniciar Fuseki:\n"
                + resultado.stderr
                + "\n"
                + resultado.stdout
            )

        # Esperar que el endpoint regrese.
        esperar_fuseki()

        # Evidencia central de persistencia.
        assert marcador_existe(sujeto), (
            "El marcador desapareció tras "
            "reiniciar Fuseki. Revisa el "
            "volumen TDB2 del contenedor."
        )

        # La ontología original permanece.
        assert contar_triples() >= 354

    finally:
        # Retirar únicamente el marcador
        # generado por esta prueba.
        if insertado:
            try:
                esperar_fuseki()
                actualizar(eliminar)

            except (
                HTTPError,
                URLError,
                TimeoutError,
                OSError
            ) as error:
                pytest.fail(
                    "No se pudo limpiar el "
                    "marcador de prueba: "
                    f"{error}"
                )

    assert not marcador_existe(sujeto)


# ---------------------------------------
# PRUEBA 3:
# COMPROBAR QUE NO SE PERDIÓ LA ONTOLOGÍA
# ---------------------------------------

def test_263_consultas_siguen_disponibles():
    resultado = consultar(
        """
        PREFIX : <http://www.semanticweb.org/user/ontologies/2026/8/untitled-ontology-20/>

        SELECT ?monto
        WHERE {
            :cuentaNequi
                :tieneMontoReservado ?monto .
        }
        """
    )

    filas = resultado[
        "results"
    ]["bindings"]

    assert len(filas) == 1

    assert float(
        filas[0]["monto"]["value"]
    ) == 400000.0
