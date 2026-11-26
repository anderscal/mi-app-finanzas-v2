
"""Conciliacion del GMF - Paso 27.8 C1.

Herramienta de auditoria independiente.
No pertenece al flujo de produccion.

No modifica datos financieros.
No publica grafos.
No llama a Gemini.
No registra credenciales.
"""

import argparse
import getpass

from collections import defaultdict
from decimal import Decimal

from app.business.errores import ErrorNegocio

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.persistence.database import engine

from app.business.auth_business_service import (
    obtener_usuario_actual,
)

from app.business.movimiento_service import (
    calcular_periodo,
)

from app.persistence.movimiento_repository import (
    obtener_movimientos_mes,
    obtener_totales_mes,
)


CERO = Decimal("0.00")


def decimal(valor):

    numero = Decimal(str(valor))

    if not numero.is_finite():

        raise ValueError(
            "Importe financiero no valido."
        )

    return numero


def conciliar(db, id_usuario, anio, mes):

    inicio, fin = calcular_periodo(
        anio,
        mes,
    )

    movimientos = obtener_movimientos_mes(
        db,
        id_usuario,
        inicio,
        fin,
    )

    totales = obtener_totales_mes(
        db,
        id_usuario,
        inicio,
        fin,
    )

    grupos = defaultdict(
        lambda: {
            "cantidad": 0,
            "gmf": CERO,
        }
    )

    ingresos_ordinarios = CERO
    gastos_ordinarios = CERO

    gmf_gastos_ordinarios = CERO
    gmf_otras_operaciones = CERO

    total_categorias = CERO

    for fila in movimientos:

        if fila["estado"] != "ACTIVO":
            continue

        tipo = fila["tipo"]
        origen = fila["origen"]

        monto = decimal(fila["monto"])

        gmf = decimal(fila["monto_gmf"])

        grupo = grupos[(tipo, origen)]

        grupo["cantidad"] += 1
        grupo["gmf"] += gmf

        if tipo == "INGRESO" and origen == "NORMAL":

            ingresos_ordinarios += monto

        if tipo == "GASTO" and origen == "NORMAL":

            gastos_ordinarios += monto

            gmf_gastos_ordinarios += gmf

            total_categorias += monto + gmf

        else:

            gmf_otras_operaciones += gmf

    gmf_calculado = (
        gmf_gastos_ordinarios
        + gmf_otras_operaciones
    )

    gmf_repository = decimal(
        totales["gmf"]
    )

    print("\nCONCILIACION DEL GMF")

    print("=" * 60)

    print(f"Periodo: {mes:02d}/{anio}")

    print(
        f"\nIngresos ordinarios: "
        f"{ingresos_ordinarios:.2f} COP"
    )

    print(
        f"Gastos ordinarios: "
        f"{gastos_ordinarios:.2f} COP"
    )

    print(
        f"GMF de gastos ordinarios: "
        f"{gmf_gastos_ordinarios:.2f} COP"
    )

    print(
        f"GMF de otras operaciones: "
        f"{gmf_otras_operaciones:.2f} COP"
    )

    print(
        f"Total gastos incluyendo su GMF: "
        f"{total_categorias:.2f} COP"
    )

    print(
        f"GMF total calculado: "
        f"{gmf_calculado:.2f} COP"
    )

    print(
        f"GMF total del repositorio: "
        f"{gmf_repository:.2f} COP"
    )

    print("\nDESGLOSE POR TIPO Y ORIGEN")

    print("-" * 60)

    for (tipo, origen), datos in sorted(
        grupos.items()
    ):

        print(
            f"Tipo: {tipo} | "
            f"Origen: {origen} | "
            f"Cantidad: {datos['cantidad']} | "
            f"GMF: {datos['gmf']:.2f} COP"
        )

    comprobaciones = {

        "Ingresos coinciden con el repositorio": (
            ingresos_ordinarios
            == decimal(totales["ingresos"])
        ),

        "Gastos coinciden con el repositorio": (
            gastos_ordinarios
            == decimal(totales["gastos"])
        ),

        "GMF completo coincide con el repositorio": (
            gmf_calculado
            == gmf_repository
        ),

        "Gastos por categoria incluyen su propio GMF": (
            total_categorias
            == gastos_ordinarios
            + gmf_gastos_ordinarios
        ),

        "Diferencia explicada por otras operaciones": (
            gmf_repository
            - gmf_gastos_ordinarios
            == gmf_otras_operaciones
        ),
    }

    print("\nCOMPROBACIONES")

    print("-" * 60)

    for nombre, correcto in comprobaciones.items():

        estado = "OK" if correcto else "FALLO"

        print(f"[{estado}] {nombre}")

    aprobadas = sum(
        comprobaciones.values()
    )

    fallos = (
        len(comprobaciones)
        - aprobadas
    )

    print("\nRESUMEN")

    print(f"Correctos: {aprobadas}")
    print(f"Fallos: {fallos}")

    return 0 if fallos == 0 else 1


def main():

    parser = argparse.ArgumentParser(
        description="Conciliacion GMF 27.8"
    )

    parser.add_argument(
        "--anio",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--mes",
        type=int,
        required=True,
    )

    args = parser.parse_args()

    if (
        not 2000 <= args.anio <= 9998
        or not 1 <= args.mes <= 12
    ):

        print("Periodo no valido.")

        return 1

    token = getpass.getpass(
        "JWT local: "
    ).strip()

    if token.lower().startswith("bearer "):

        token = token[7:].strip()

    if not token:

        print("No se proporciono un JWT.")

        return 1

    try:

        with Session(engine) as db:

            # Una instantanea consistente.
            # PostgreSQL impide escrituras.

            db.execute(
                text(
                    "SET TRANSACTION "
                    "ISOLATION LEVEL REPEATABLE READ, "
                    "READ ONLY"
                )
            )

            usuario = obtener_usuario_actual(
                token=token,
                db=db,
            )

            resultado = conciliar(
                db,
                usuario.id_usuario,
                args.anio,
                args.mes,
            )

            db.rollback()

            return resultado

    except ErrorNegocio:

        print(
            "JWT no valido o vencido. "
            "Inicia sesion nuevamente."
        )

        return 1

    except Exception as error:

        # Evita mostrar parametros de conexion
        # o informacion financiera en errores.

        print(
            "Error de auditoria: "
            f"{type(error).__name__}"
        )

        return 1


if __name__ == "__main__":

    raise SystemExit(main())
