from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.persistence.anulacion_repository import (
    bloquear_movimiento_usuario,
    bloquear_movimientos_transferencia,
    bloquear_transferencia,
    bloquear_obligacion_anulacion,
)

from app.persistence.obligacion_escritura_repository import (
    obtener_abonos_obligacion,
)


def recalcular_estado_obligacion(
    db: Session,
    obligacion
):
    if obligacion.tipo_obligacion == "POR_PAGAR":
        tipo = "GASTO"

    elif obligacion.tipo_obligacion == "POR_COBRAR":
        tipo = "INGRESO"

    else:
        raise HTTPException(
            status_code=409,
            detail="Tipo de obligación no válido"
        )

    movimientos = obtener_abonos_obligacion(
        db,
        obligacion.id_obligacion,
        tipo
    )

    total_abonado = sum(
        (
            movimiento.monto
            for movimiento in movimientos
            if movimiento.estado == "ACTIVO"
        ),
        Decimal("0.00")
    )

    pendiente = (
        obligacion.monto_original
        - total_abonado
    )

    if pendiente <= 0:
        obligacion.estado = "SALDADA"
    else:
        obligacion.estado = "ACTIVA"


def anular_movimiento(
    db: Session,
    id_usuario: int,
    id_movimiento: int
):
    if id_usuario <= 0:
        raise HTTPException(
            status_code=401,
            detail="Usuario no válido"
        )

    try:
        movimiento = bloquear_movimiento_usuario(
            db,
            id_movimiento,
            id_usuario
        )

        if movimiento is None:
            raise HTTPException(
                status_code=404,
                detail="Movimiento no encontrado"
            )

        if movimiento.estado == "ANULADO":
            raise HTTPException(
                status_code=409,
                detail="El movimiento ya está anulado"
            )

        # ---------------------------------
        # CASO 1: MOVIMIENTO NORMAL
        # ---------------------------------

        if movimiento.origen == "NORMAL":

            movimiento.estado = "ANULADO"

            db.commit()

            return {
                "id_movimiento":
                    movimiento.id_movimiento,

                "estado":
                    "ANULADO",

                "mensaje":
                    "Movimiento normal anulado correctamente"
            }

        # ---------------------------------
        # CASO 2: TRANSFERENCIA
        # ---------------------------------

        if movimiento.origen == "TRANSFERENCIA":

            if movimiento.id_transferencia is None:
                raise HTTPException(
                    status_code=409,
                    detail="Transferencia inconsistente"
                )

            transferencia = bloquear_transferencia(
                db,
                movimiento.id_transferencia
            )

            if transferencia is None:
                raise HTTPException(
                    status_code=409,
                    detail="Transferencia no encontrada"
                )

            movimientos = bloquear_movimientos_transferencia(
                db,
                movimiento.id_transferencia
            )

            if len(movimientos) != 2:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "La transferencia no tiene "
                        "los dos movimientos esperados"
                    )
                )

            for mov in movimientos:
                mov.estado = "ANULADO"

            transferencia.estado = "ANULADA"

            db.commit()

            return {
                "id_movimiento":
                    movimiento.id_movimiento,

                "estado":
                    "ANULADO",

                "mensaje":
                    "Transferencia anulada correctamente"
            }

        # ---------------------------------
        # CASO 3: OBLIGACIÓN
        # ---------------------------------

        if movimiento.origen == "OBLIGACION":

            if movimiento.id_obligacion is None:
                raise HTTPException(
                    status_code=409,
                    detail="Movimiento de obligación inconsistente"
                )

            obligacion = bloquear_obligacion_anulacion(
                db,
                movimiento.id_obligacion
            )

            if obligacion is None:
                raise HTTPException(
                    status_code=409,
                    detail="Obligación no encontrada"
                )

            movimiento.estado = "ANULADO"

            # Flush para que la consulta posterior
            # vea el nuevo estado dentro de la
            # misma transacción.
            db.flush()

            recalcular_estado_obligacion(
                db,
                obligacion
            )

            db.commit()

            return {
                "id_movimiento":
                    movimiento.id_movimiento,

                "estado":
                    "ANULADO",

                "mensaje":
                    "Movimiento de obligación anulado correctamente"
            }

        raise HTTPException(
            status_code=409,
            detail="Origen de movimiento no válido"
        )

    except IntegrityError as error:
        db.rollback()

        print("\n=== ERROR POSTGRESQL ===")
        print(error.orig)
        print("========================\n")

        raise HTTPException(
            status_code=409,
            detail="Conflicto de integridad al anular"
        )

    except Exception:
        db.rollback()
        raise