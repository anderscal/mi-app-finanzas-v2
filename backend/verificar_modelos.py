
from sqlalchemy import inspect

import app.models
from app.database.base import Base
from app.persistence.database import engine


modelos = Base.metadata.tables.keys()
inspector = inspect(engine)
tablas_reales = inspector.get_table_names()

print("=== MODELOS SQLALCHEMY ===")

for nombre in sorted(modelos):
    print(nombre)

print("\n=== COMPROBACIÓN ===")

for nombre in sorted(modelos):
    if nombre not in tablas_reales:
        print(f"FALTA EN POSTGRESQL: {nombre}")
        continue

    columnas_modelo = set(
        Base.metadata.tables[nombre].columns.keys()
    )

    columnas_bd = {
        columna["name"]
        for columna in inspector.get_columns(nombre)
    }

    faltantes = columnas_modelo - columnas_bd
    adicionales = columnas_bd - columnas_modelo

    if not faltantes and not adicionales:
        print(f"OK: {nombre}")
    else:
        print(f"REVISAR: {nombre}")
        print("No existen en BD:", faltantes)
        print("No existen en ORM:", adicionales)
