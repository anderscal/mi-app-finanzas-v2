"""Configuracion segura de las pruebas.

Las pruebas de integracion requieren una base PostgreSQL
independiente, configurada en backend/.env.test.
"""

import os

from pathlib import Path

import pytest

from dotenv import dotenv_values, load_dotenv


BACKEND = Path(
    __file__
).resolve().parents[2]

ARCHIVO_APP = BACKEND / ".env"

ARCHIVO_TEST = BACKEND / ".env.test"


VARIABLES_DB = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)


# Cargar primero la configuracion normal.
# No imprimir credenciales.

load_dotenv(
    dotenv_path=ARCHIVO_APP
)


def destino(datos):

    return (
        str(
            datos.get("DB_HOST") or ""
        ).strip().lower().rstrip("."),

        str(
            datos.get("DB_NAME") or ""
        ).strip(),
    )


DESTINOS_APLICACION = {
    destino(dotenv_values(ARCHIVO_APP)),
    destino(os.environ),
}


BASE_PRUEBAS_CONFIGURADA = False


if ARCHIVO_TEST.is_file():

    datos_test = dotenv_values(
        ARCHIVO_TEST
    )

    faltantes = [

        variable

        for variable in VARIABLES_DB

        if not datos_test.get(variable)
    ]

    if faltantes:

        raise pytest.UsageError(
            "Variables faltantes en .env.test: "
            + ", ".join(faltantes)
        )

    try:

        puerto = int(
            datos_test["DB_PORT"]
        )

        if not 1 <= puerto <= 65535:

            raise ValueError()

    except ValueError as error:

        raise pytest.UsageError(
            "DB_PORT invalido en .env.test"
        ) from error

    if destino(datos_test) in DESTINOS_APLICACION:

        raise pytest.UsageError(
            "La base de pruebas coincide con la "
            "base configurada para la aplicacion. "
            "Utiliza una base o rama independiente."
        )

    # Configurar antes de importar app.main
    # y antes de crear el motor PostgreSQL.

    for variable in VARIABLES_DB:

        os.environ[variable] = datos_test[
            variable
        ]

    BASE_PRUEBAS_CONFIGURADA = True


from fastapi.testclient import TestClient

from sqlalchemy import event

from sqlalchemy.orm import Session

from app.main import app

from app.persistence.database import (
    engine,
    get_db,
)


if BASE_PRUEBAS_CONFIGURADA:

    destino_motor = (
        str(engine.url.host or "")
        .strip().lower().rstrip("."),

        str(engine.url.database or ""),
    )

    if destino_motor != destino(datos_test):

        raise pytest.UsageError(
            "El motor PostgreSQL no utiliza "
            "la configuracion de pruebas."
        )

else:

    # Las pruebas aisladas pueden ejecutarse
    # sin .env.test.
    #
    # Bloqueamos conexiones del motor principal
    # para impedir accesos accidentales.

    def bloquear_conexion(
        dialect,
        conn_rec,
        cargs,
        cparams,
    ):

        raise RuntimeError(
            "Conexion bloqueada durante pytest. "
            "Configura una base independiente "
            "en backend/.env.test."
        )

    event.listen(
        engine,
        "do_connect",
        bloquear_conexion,
    )


@pytest.fixture
def db_session():

    if not BASE_PRUEBAS_CONFIGURADA:

        pytest.fail(
            "Las pruebas de integracion requieren "
            "una base independiente en .env.test.",
            pytrace=False,
        )

    with engine.connect() as connection:

        transaction = connection.begin()

        session = Session(
            bind=connection,

            join_transaction_mode="create_savepoint",
        )

        try:

            yield session

        finally:

            session.close()

            if transaction.is_active:

                transaction.rollback()


@pytest.fixture
def client(db_session):

    def override_get_db():

        yield db_session

    anterior = app.dependency_overrides.get(
        get_db
    )

    app.dependency_overrides[
        get_db
    ] = override_get_db

    try:

        with TestClient(app) as test_client:

            yield test_client

    finally:

        if anterior is None:

            app.dependency_overrides.pop(
                get_db,
                None,
            )

        else:

            app.dependency_overrides[
                get_db
            ] = anterior