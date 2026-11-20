
"""
Paso 25.1A.

Crear la tabla aporte_meta para registrar
reservas y liberaciones de dinero asociadas
a metas y cuentas financieras.

No modifica registros existentes.

La migración es idempotente.
"""

from sqlalchemy import inspect

from app.persistence.database import engine

# Importar todos los modelos para resolver
# las llaves foráneas en SQLAlchemy.
from app.models import AporteMeta


TABLA = "aporte_meta"

COLUMNAS_ESPERADAS = {
    "id_aporte",
    "uuid_operacion",
    "id_usuario",
    "id_meta",
    "id_cuenta",
    "tipo",
    "monto",
    "fecha_operacion",
    "estado",
    "creado_en",
}

RESTRICCIONES_ESPERADAS = {
    "ck_aporte_meta_monto",
    "ck_aporte_meta_tipo",
    "ck_aporte_meta_estado",
}

INDICES_ESPERADOS = {
    "ix_aporte_meta_usuario_cuenta",
    "ix_aporte_meta_usuario_meta",
}


def verificar_estructura(conexion):
    inspector = inspect(conexion)

    if not inspector.has_table(TABLA):
        raise RuntimeError(
            "No se encontró la tabla aporte_meta."
        )

    columnas = {
        item["name"]
        for item in inspector.get_columns(TABLA)
    }

    faltantes = COLUMNAS_ESPERADAS - columnas

    if faltantes:
        raise RuntimeError(
            "Faltan columnas en aporte_meta: "
            + ", ".join(sorted(faltantes))
        )

    checks = {
        item["name"]
        for item in inspector.get_check_constraints(TABLA)
    }

    faltantes_checks = (
        RESTRICCIONES_ESPERADAS - checks
    )

    if faltantes_checks:
        raise RuntimeError(
            "Faltan restricciones CHECK: "
            + ", ".join(sorted(faltantes_checks))
        )

    indices = {
        item["name"]
        for item in inspector.get_indexes(TABLA)
    }

    faltantes_indices = INDICES_ESPERADOS - indices

    if faltantes_indices:
        raise RuntimeError(
            "Faltan índices: "
            + ", ".join(sorted(faltantes_indices))
        )

    restricciones_unicas = {
        item["name"]
        for item in inspector.get_unique_constraints(TABLA)
    }

    if (
        "uq_aporte_meta_uuid"
        not in restricciones_unicas
    ):
        raise RuntimeError(
            "Falta la restricción de UUID único."
        )


def ejecutar():
    print("Verificando la tabla aporte_meta...")

    with engine.begin() as conexion:
        inspector = inspect(conexion)

        if inspector.has_table(TABLA):
            verificar_estructura(conexion)

            print(
                "La tabla ya existe con la "
                "estructura esperada."
            )

        else:
            AporteMeta.__table__.create(
                bind=conexion,
                checkfirst=False
            )

            verificar_estructura(conexion)

            print(
                "Tabla aporte_meta creada correctamente."
            )

    print()
    print("Migración 25.1A completada.")
    print("No se modificaron saldos bancarios.")
    print("No se modificaron aportes anteriores.")


if __name__ == "__main__":
    ejecutar()
