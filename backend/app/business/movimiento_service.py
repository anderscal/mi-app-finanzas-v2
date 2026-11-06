
from datetime import date

from sqlalchemy.orm import Session

from app.persistence.movimiento_repository import (
    obtener_movimientos_mes,
    obtener_totales_mes
)


def calcular_periodo(anio: int, mes: int):
    if not 2000 <= anio <= 9999:
        raise ValueError("El año no es válido")

    if not 1 <= mes <= 12:
        raise ValueError("El mes debe estar entre 1 y 12")

    inicio = date(anio, mes, 1)

    if mes == 12:
        fin = date(anio + 1, 1, 1)
    else:
        fin = date(anio, mes + 1, 1)

    return inicio, fin


def consultar_resumen_mensual(
    db: Session,
    id_usuario: int,
    anio: int,
    mes: int
):
    if id_usuario <= 0:
        raise ValueError("El usuario no es válido")

    inicio, fin = calcular_periodo(anio, mes)

    totales = obtener_totales_mes(
        db, id_usuario, inicio, fin
    )

    ingresos = totales["ingresos"]
    gastos = totales["gastos"]
    gmf = totales["gmf"]

    return {
        "anio": anio,
        "mes": mes,
        "ingresos_ordinarios": ingresos,
        "gastos_ordinarios": gastos,
        "balance_ordinario": ingresos - gastos,
        "gmf_total": gmf
    }


def consultar_historial_mensual(
    db: Session,
    id_usuario: int,
    anio: int,
    mes: int
):
    if id_usuario <= 0:
        raise ValueError("El usuario no es válido")

    inicio, fin = calcular_periodo(anio, mes)

    registros = obtener_movimientos_mes(
        db, id_usuario, inicio, fin
    )

    movimientos = [dict(fila) for fila in registros]

    return {
        "anio": anio,
        "mes": mes,
        "total_movimientos": len(movimientos),
        "movimientos": movimientos
    }
