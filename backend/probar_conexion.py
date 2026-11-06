
from sqlalchemy import text

from app.persistence.database import engine

try:
    with engine.connect() as conexion:
        resultado = conexion.execute(
            text("SELECT current_database()")
        )

        nombre_bd = resultado.scalar()

        print("Conexión exitosa a PostgreSQL")
        print(f"Base de datos: {nombre_bd}")

except Exception as error:
    print("Error al conectar con PostgreSQL")
    print(f"Tipo de error: {type(error).__name__}")
