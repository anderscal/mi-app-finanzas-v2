from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Movimiento

from app.persistence.movimiento_escritura_repository import (
    calcular_saldo_cuenta,
)

from app.persistence.obligacion_escritura_repository import (
    agregar_movimiento_obligacion,
    bloquear_cuenta_obligacion,
    bloquear_obligacion,
    buscar_movimiento_obligacion_uuid,
    obtener_abonos_obligacion,
)

from app.schemas.movimiento_schema import (
    AbonoObligacionCrear,
)


def calcular_pendiente(
    db: Session,
    obligacion
) -> Decimal:

    if obligacion.tipo_obligacion == "POR_PAGAR":
        tipo_movimiento = "GASTO"

    elif obligacion.tipo_obligacion == "POR_COBRAR":
        tipo_movimiento = "INGRESO"

    else:
        raise HTTPException(
            status_code=409,
            detail="Tipo de obligación no válido"
        )

    movimientos = obtener_abonos_obligacion(
        db,
        obligacion.id_obligacion,
        tipo_movimiento
    )

    abonado = sum(
        (
            movimiento.monto
            for movimiento in movimientos
        ),
        Decimal("0.00")
    )

    return obligacion.monto_original - abonado


def misma_operacion(
    movimiento: Movimiento,
    datos: AbonoObligacionCrear,
    tipo: str
):
    return (
        movimiento.id_cuenta == datos.id_cuenta
        and movimiento.id_obligacion
        == datos.id_obligacion
        and movimiento.tipo == tipo
        and movimiento.origen == "OBLIGACION"
        and movimiento.monto == datos.monto
        and movimiento.fecha_movimiento
        == datos.fecha_movimiento
        and movimiento.descripcion
        == datos.descripcion
    )


def registrar_abono_obligacion(
    db: Session,
    id_usuario: int,
    datos: AbonoObligacionCrear
):
    try:

        # 1. Bloquear obligación
        obligacion = bloquear_obligacion(
            db,
            datos.id_obligacion,
            id_usuario
        )

        if obligacion is None:
            raise HTTPException(
                status_code=404,
                detail="Obligación no encontrada"
            )

        if obligacion.estado != "ACTIVA":
            raise HTTPException(
                status_code=409,
                detail="La obligación no está activa"
            )

        # 2. Determinar dirección del movimiento
        if obligacion.tipo_obligacion == "POR_PAGAR":
            tipo_movimiento = "GASTO"

        elif obligacion.tipo_obligacion == "POR_COBRAR":
            tipo_movimiento = "INGRESO"

        else:
            raise HTTPException(
                status_code=409,
                detail="Tipo de obligación no válido"
            )

        # 3. Revisar idempotencia
        existente = buscar_movimiento_obligacion_uuid(
            db,
            datos.uuid_local
        )

        if existente is not None:

            if not misma_operacion(
                existente,
                datos,
                tipo_movimiento
            ):
                raise HTTPException(
                    status_code=409,
                    detail="UUID utilizado por otra operación"
                )

            pendiente = calcular_pendiente(
                db,
                obligacion
            )

            resultado = {
                "id_movimiento":
                    existente.id_movimiento,

                "id_obligacion":
                    obligacion.id_obligacion,

                "uuid_local":
                    existente.uuid_local,

                "tipo":
                    existente.tipo,

                "monto":
                    existente.monto,

                "monto_pendiente":
                    pendiente,

                "creado":
                    False,

                "mensaje":
                    "Abono previamente registrado"
            }

            db.rollback()

            return resultado

        # 4. Bloquear cuenta
        cuenta = bloquear_cuenta_obligacion(
            db,
            datos.id_cuenta,
            id_usuario
        )

        if cuenta is None:
            raise HTTPException(
                status_code=404,
                detail="Cuenta no encontrada"
            )

        if cuenta.estado != "ACTIVA":
            raise HTTPException(
                status_code=409,
                detail="La cuenta está inactiva"
            )

        # 5. Calcular pendiente
        pendiente_actual = calcular_pendiente(
            db,
            obligacion
        )

        if pendiente_actual <= 0:
            raise HTTPException(
                status_code=409,
                detail="La obligación ya está saldada"
            )

        if datos.monto > pendiente_actual:
            raise HTTPException(
                status_code=409,
                detail=(
                    "El abono supera el monto pendiente"
                )
            )

        # 6. Si es POR_PAGAR, comprobar saldo
        if tipo_movimiento == "GASTO":

            saldo = calcular_saldo_cuenta(
                db,
                cuenta
            )

            if saldo < datos.monto:
                raise HTTPException(
                    status_code=409,
                    detail="Saldo insuficiente"
                )

        # 7. Crear movimiento
        movimiento = Movimiento(
            uuid_local=datos.uuid_local,

            id_cuenta=datos.id_cuenta,

            id_categoria=None,

            id_transferencia=None,

            id_obligacion=
                obligacion.id_obligacion,

            tipo=tipo_movimiento,

            origen="OBLIGACION",

            monto=datos.monto,

            fecha_movimiento=
                datos.fecha_movimiento,

            descripcion=
                datos.descripcion,

            aplica_gmf=False,

            monto_gmf=Decimal("0.00"),

            estado="ACTIVO"
        )

        agregar_movimiento_obligacion(
            db,
            movimiento
        )

        nuevo_pendiente = (
            pendiente_actual - datos.monto 
        )
        if nuevo_pendiente == Decimal("0.00"):
            obligacion.estado = "SALDADA"

        resultado = {
    "id_movimiento":
        movimiento.id_movimiento,

    "id_obligacion":
        obligacion.id_obligacion,

    "uuid_local":
        movimiento.uuid_local,

    "tipo":
        movimiento.tipo,

    "monto":
        movimiento.monto,

    "monto_pendiente":
        nuevo_pendiente,

    "creado":
        True,

    "mensaje":
        "Abono registrado correctamente"
}

        db.commit()

        return resultado

    except IntegrityError as error:
        db.rollback()

        print("\n=== ERROR POSTGRESQL ===")
        print(error.orig)
        print("========================\n")

        raise HTTPException(
            status_code=409,
            detail=(
                "Conflicto de integridad "
                "al registrar el abono"
            )
        )

    except Exception:
        db.rollback()
        raise