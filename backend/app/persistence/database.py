
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import Session

# Cargar las variables del archivo .env
load_dotenv()

# Crear la configuración de conexión
database_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME")
)

# Crear el motor de conexión
engine = create_engine(
    database_url,
    pool_pre_ping=True
)

# Proporcionar una sesión por solicitud
def get_db():
    with Session(engine) as session:
        yield session
