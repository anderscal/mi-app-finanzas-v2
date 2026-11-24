
import json
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest


# --------------------------------------
# CONFIGURACION DE FUSEKI
# --------------------------------------

ENDPOINT = (
    "http://127.0.0.1:3030/"
    "finanzas_demo/sparql"
)

BASE = (
    Path(__file__).resolve().parents[2]
    / "semantica"
)

CONSULTAS = BASE / "consultas"


# --------------------------------------
# CLIENTE SPARQL DE SOLO LECTURA
# --------------------------------------

def ejecutar_sparql(consulta: str) -> dict:
    cuerpo = urlencode({
        "query": consulta
    }).encode("utf-8")

    solicitud = Request(
        ENDPOINT,
        data=cuerpo,
        headers={
            "Content-Type":
                "application/x-www-form-urlencoded",

            "Accept":
                "application/sparql-results+json",
        },
        method="POST",
    )

    try:
        with urlopen(
            solicitud,
            timeout=10
        ) as respuesta:
            contenido = respuesta.read()

    except HTTPError as error:
        detalle = error.read(
            1000
        ).decode(
            "utf-8",
            errors="replace"
        )

        pytest.fail(
            f"Fuseki devolvio HTTP {error.code}. "
            f"Detalle: {detalle}"
        )

    except (
        URLError,
        TimeoutError,
        OSError
    ) as error:
        pytest.fail(
            "No fue posible conectar con Apache Jena "
            f"Fuseki en {ENDPOINT}. "
            "Comprueba que el servidor este iniciado "
            "y que exista el dataset finanzas_demo. "
            f"Error: {error}"
        )

    try:
        resultado = json.loads(
            contenido.decode("utf-8")
        )

    except (
        ValueError,
        UnicodeError
    ) as error:
        pytest.fail(
            "Fuseki no devolvio JSON SPARQL valido: "
            f"{error}"
        )

    return resultado


def filas_sparql(nombre_archivo: str) -> list:
    ruta = CONSULTAS / nombre_archivo

    assert ruta.is_file(), (
        f"No existe la consulta: {ruta}"
    )

    texto = ruta.read_text(
        encoding="utf-8"
    )

    respuesta = ejecutar_sparql(
        texto
    )

    assert "results" in respuesta, (
        "Fuseki no devolvio resultados SELECT"
    )

    return respuesta["results"]["bindings"]


def valor(fila: dict, variable: str) -> str:
    assert variable in fila, (
        f"Falta la variable SPARQL: {variable}"
    )

    return fila[variable]["value"]


# --------------------------------------
# PRUEBA 1
# DATASET Y TRIPLES CARGADOS
# --------------------------------------

def test_262_dataset_disponible_con_ontologia():
    respuesta = ejecutar_sparql(
        """
        SELECT (COUNT(*) AS ?total)
        WHERE {
            ?s ?p ?o .
        }
        """
    )

    registros = respuesta[
        "results"
    ]["bindings"]

    assert len(registros) == 1

    total = int(
        valor(
            registros[0],
            "total"
        )
    )

    # El TTL adjunto tiene 354 triples.
    # Se permite ampliarlo sin romper la prueba.
    assert total >= 354, (
        "El dataset parece incompleto. "
        f"Solo se encontraron {total} triples."
    )


# --------------------------------------
# PRUEBA 2
# CATEGORIAS Y CLASIFICACIONES
# --------------------------------------

def test_262_consulta_clasificacion_gastos():
    filas = filas_sparql(
        "01_clasificacion_gastos.rq"
    )

    assert len(filas) >= 4

    restaurantes = [
        fila for fila in filas
        if valor(fila, "categoria").endswith(
            "/restaurantes"
        )
    ]

    assert len(restaurantes) == 1

    categoria = restaurantes[0]

    assert valor(
        categoria,
        "nombre"
    ) == "Restaurantes"

    assert valor(
        categoria,
        "naturaleza"
    ).endswith(
        "/discrecional"
    )

    assert valor(
        categoria,
        "comportamiento"
    ).endswith(
        "/variable"
    )


# --------------------------------------
# PRUEBA 3
# RESERVAS NETAS VIA SPARQL HTTP
# --------------------------------------

def test_262_reservas_netas():
    filas = filas_sparql(
        "02_reservas_netas.rq"
    )

    resultado = [
        fila for fila in filas
        if (
            valor(fila, "meta").endswith(
                "/metaViaje"
            )
            and valor(
                fila,
                "cuenta"
            ).endswith(
                "/cuentaNequi"
            )
        )
    ]

    assert len(resultado) == 1

    neto = Decimal(
        valor(
            resultado[0],
            "neto"
        )
    )

    assert neto == Decimal("400000.00")


# --------------------------------------
# PRUEBA 4
# SALDOS DE LA CUENTA DEMOSTRATIVA
# --------------------------------------

def test_262_saldos_demostrativos():
    filas = filas_sparql(
        "03_saldos_demo.rq"
    )

    nequi = [
        fila for fila in filas
        if valor(
            fila,
            "cuenta"
        ).endswith(
            "/cuentaNequi"
        )
    ]

    assert len(nequi) == 1

    fila = nequi[0]

    real = Decimal(
        valor(fila, "real")
    )

    reservado = Decimal(
        valor(fila, "reservado")
    )

    libre = Decimal(
        valor(fila, "libre")
    )

    assert real == Decimal("1000000.00")
    assert reservado == Decimal("400000.00")
    assert libre == Decimal("600000.00")

    assert real - reservado == libre
