
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.persistence.planificacion_repository import (
    obtener_presupuestos,
    obtener_metas,
    obtener_obligaciones,
)


def porcentaje(parte: Decimal, total: Decimal):
    if total <= 0:
        raise ValueError("El total debe ser positivo")

    return (
        parte / total * Decimal("100")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def consultar_planificacion(db: Session, id_usuario: int):

    if id_usuario <= 0:
        raise ValueError("El usuario debe ser positivo")

    # PRESUPUESTOS
    presupuestos = []

    for fila in obtener_presupuestos(db, id_usuario):
        limite = fila["monto_limite"]
        gastado = fila["gastado"]

        presupuestos.append({
            "id_presupuesto": fila["id_presupuesto"],
            "categoria": fila["nombre_categoria"],
            "anio": fila["anio"],
            "mes": fila["mes"],
            "monto_limite": limite,
            "gastado": gastado,
            "disponible": limite - gastado,
            "porcentaje_usado": porcentaje(gastado, limite)
        })

    # METAS
    metas = []

    for meta in obtener_metas(db, id_usuario):
        metas.append({
            "id_meta": meta.id_meta,
            "nombre_meta": meta.nombre_meta,
            "monto_objetivo": meta.monto_objetivo,
            "monto_acumulado": meta.monto_acumulado,
            "porcentaje_progreso": porcentaje(
                meta.monto_acumulado,
                meta.monto_objetivo
            ),
            "estado": meta.estado
        })

    # OBLIGACIONES
    obligaciones = []

    for fila in obtener_obligaciones(db, id_usuario):
        pendiente = (
            fila["monto_original"] - fila["total_abonado"]
        )

        obligaciones.append({
            "id_obligacion": fila["id_obligacion"],
            "nombre_obligacion": fila["nombre_obligacion"],
            "tipo_obligacion": fila["tipo_obligacion"],
            "monto_original": fila["monto_original"],
            "total_abonado": fila["total_abonado"],
            "monto_pendiente": pendiente,
            "estado": fila["estado"]
        })

    return {
        "id_usuario": id_usuario,
        "presupuestos": presupuestos,
        "metas": metas,
        "obligaciones": obligaciones
    }
