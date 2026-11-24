"""Conexion PostgreSQL y sesiones de la aplicacion.

Capa Persistence.

La inicializacion de los eventos de sincronizacion RDF
se realiza desde el punto de composicion de la aplicacion.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session


load_dotenv()


database_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME"),
)


engine = create_engine(
    database_url,
    pool_pre_ping=True,
)


class SesionFinanciera(Session):
    """Sesion utilizada por las solicitudes financieras."""


def get_db():

    with SesionFinanciera(engine) as session:

        yield session