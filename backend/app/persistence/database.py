"""Conexion PostgreSQL y sesiones de la aplicacion."""

import os

import certifi

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session


LOCALES = {
    "127.0.0.1",
    "localhost",
    "::1",
}


def crear_url_postgresql(config):

    host = (
        config.get("DB_HOST")
        or "127.0.0.1"
    ).strip()

    if not host or any(
        c.isspace() for c in host
    ):

        raise ValueError("DB_HOST invalido")


    opciones = {
        "connect_timeout": "10"
    }


    if host.lower() in LOCALES:

        opciones["sslmode"] = "prefer"

    else:

        opciones.update({

            "sslmode": "verify-full",

            "sslrootcert": certifi.where(),

            "channel_binding": "require",

            "gssencmode": "disable",
        })


    return URL.create(

        drivername="postgresql+psycopg",

        username=config.get("DB_USER"),

        password=config.get("DB_PASSWORD"),

        host=host,

        port=int(
            config.get("DB_PORT", "5432")
        ),

        database=config.get("DB_NAME"),

        query=opciones,
    )


load_dotenv()


database_url = crear_url_postgresql(
    os.environ
)


engine = create_engine(

    database_url,

    pool_pre_ping=True,

    pool_size=3,

    max_overflow=2,

    pool_timeout=15,

    pool_recycle=300,
)


class SesionFinanciera(Session):

    """Sesion utilizada por las solicitudes financieras."""


def get_db():

    with SesionFinanciera(engine) as session:

        yield session