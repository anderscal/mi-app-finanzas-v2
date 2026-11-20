
"""
Migración de estados de obligaciones y metas.

Objetivo:
Permitir el estado INACTIVA en PostgreSQL,
sin eliminar compatibilidad con CANCELADA.

No modifica registros financieros existentes.
No cambia saldos, movimientos ni aportes.

La ejecución es transaccional e idempotente.
"""

from sqlalchemy import inspect, text

from app.persistence.database import engine


CAMBIOS = [
    {
        "tabla": "obligacion_financiera",
        "restriccion": "ck_obligacion_estado",
        "estados_anteriores": (
            "ACTIVA",
            "SALDADA",
            "CANCELADA",
        ),
        "estados_permitidos": (
            "ACTIVA",
            "SALDADA",
            "CANCELADA",
            "INACTIVA",
        ),
    },
    {
        "tabla": "meta_financiera",
        "restriccion": "ck_meta_estado",
        "estados_anteriores": (
            "ACTIVA",
            "CUMPLIDA",
            "CANCELADA",
        ),
        "estados_permitidos": (
            "ACTIVA",
            "CUMPLIDA",
            "CANCELADA",
            "INACTIVA",
        ),
    },
]


def contiene_estados(definicion, estados):
    return all(
        f"'{estado}'" in definicion
        for estado in estados
    )


def ejecutar_migracion():
    print("Verificando restricciones financieras...")

    # Todas las modificaciones se ejecutan
    # dentro de una sola transacción.
    # Si alguna falla, PostgreSQL revierte ambas.
    with engine.begin() as conexion:
        inspector = inspect(conexion)

        for cambio in CAMBIOS:
            tabla = cambio["tabla"]
            nombre = cambio["restriccion"]

            restricciones = {
                item["name"]: item["sqltext"]
                for item in inspector.get_check_constraints(
                    tabla
                )
            }

            if nombre not in restricciones:
                raise RuntimeError(
                    f"No existe la restricción esperada: "
                    f"{tabla}.{nombre}. "
                    "No se modificó la estructura."
                )

            definicion = restricciones[nombre]

            if contiene_estados(
                definicion,
                cambio["estados_permitidos"]
            ):
                print(
                    f"{tabla}: ya admite INACTIVA."
                )
                continue

            if not contiene_estados(
                definicion,
                cambio["estados_anteriores"]
            ):
                raise RuntimeError(
                    f"La restricción {nombre} "
                    "es diferente a la esperada. "
                    "Se detuvo la migración por seguridad."
                )

            estados_sql = ", ".join(
                f"'{estado}'"
                for estado in cambio["estados_permitidos"]
            )

            print(
                f"Actualizando restricción de {tabla}..."
            )

            conexion.execute(
                text(
                    f"ALTER TABLE {tabla} "
                    f"DROP CONSTRAINT {nombre}"
                )
            )

            conexion.execute(
                text(
                    f"ALTER TABLE {tabla} "
                    f"ADD CONSTRAINT {nombre} "
                    f"CHECK (estado IN ({estados_sql}))"
                )
            )

    # Comprobación posterior al COMMIT.
    inspector = inspect(engine)

    for cambio in CAMBIOS:
        restricciones = {
            item["name"]: item["sqltext"]
            for item in inspector.get_check_constraints(
                cambio["tabla"]
            )
        }

        definicion = restricciones.get(
            cambio["restriccion"],
            ""
        )

        if not contiene_estados(
            definicion,
            cambio["estados_permitidos"]
        ):
            raise RuntimeError(
                "La verificación final falló para "
                + cambio["tabla"]
            )

    print()
    print("Migración completada correctamente.")
    print("Obligaciones: INACTIVA habilitada.")
    print("Metas: INACTIVA habilitada.")
    print("No se modificaron registros financieros.")


if __name__ == "__main__":
    ejecutar_migracion()
