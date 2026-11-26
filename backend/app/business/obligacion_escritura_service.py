
from decimal import Decimal

from app.business.errores import CodigoError, ErrorNegocio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Movimiento

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

from app.business.saldo_libre_service import (
    exigir_saldo_libre,
)


CERO = Decimal("0.00")


def tipo_abono_obligacion(obligacion) -> str:
    if obligacion.tipo_obligacion == "POR_PAGAR":
        return "GASTO"

    if obligacion.tipo_obligacion == "POR_COBRAR":
        return "INGRESO"

    raise ErrorNegocio(
        codigo=CodigoError.CONFLICTO,
        detalle="Tipo de obligación no válido"
    )


def calcular_pendiente(
    db: Session,
    obligacion
) -> Decimal:
    tipo = tipo_abono_obligacion(
        obligacion
    )

    movimientos = obtener_abonos_obligacion(
        db,
        obligacion.id_obligacion,
        tipo
    )

    total_abonado = sum(
        (m.monto for m in movimientos),
        CERO
    )

    return obligacion.monto_original - total_abonado


def misma_operacion(
    movimiento: Movimiento,
    datos: AbonoObligacionCrear,
    tipo: str
) -> bool:
    return (
        movimiento.id_cuenta == datos.id_cuenta
        and movimiento.id_obligacion == datos.id_obligacion
        and movimiento.tipo == tipo
        and movimiento.origen == "OBLIGACION"
        and movimiento.monto == datos.monto
        and movimiento.fecha_movimiento == datos.fecha_movimiento
        and movimiento.descripcion == datos.descripcion
        and movimiento.estado == "ACTIVO"
    )


def respuesta_abono(
    movimiento: Movimiento,
    obligacion,
    pendiente: Decimal,
    creado: bool
):
    return {
        "id_movimiento": movimiento.id_movimiento,
        "id_obligacion": obligacion.id_obligacion,
        "uuid_local": movimiento.uuid_local,
        "tipo": movimiento.tipo,
        "monto": movimiento.monto,
        "monto_pendiente": pendiente,
        "creado": creado,
        "mensaje": (
            "Abono registrado correctamente"
            if creado
            else "Abono previamente registrado"
        ),
    }


def registrar_abono_obligacion(
    db: Session,
    id_usuario: int,
    datos: AbonoObligacionCrear
):
    if id_usuario <= 0:
        raise ErrorNegocio(
            codigo=CodigoError.NO_AUTENTICADO,
            detalle="Usuario no válido"
        )

    try:
        # El bloqueo serializa los pagos de
        # una misma obligación.
        obligacion = bloquear_obligacion(
            db,
            datos.id_obligacion,
            id_usuario
        )

        if obligacion is None:
            raise ErrorNegocio(
                codigo=CodigoError.NO_ENCONTRADO,
                detalle="Obligación no encontrada"
            )

        tipo = tipo_abono_obligacion(
            obligacion
        )

        # Revisar UUID ANTES del estado SALDADA.
        # Un reintento válido no debe fallar porque
        # el pago anterior completó la obligación.
        existente = buscar_movimiento_obligacion_uuid(
            db,
            datos.uuid_local
        )

        if existente is not None:
            if not misma_operacion(
                existente,
                datos,
                tipo
            ):
                raise ErrorNegocio(
                    codigo=CodigoError.CONFLICTO,
                    detalle="UUID utilizado por otra operación"
                )

            pendiente = calcular_pendiente(
                db,
                obligacion
            )

            resultado = respuesta_abono(
                existente,
                obligacion,
                pendiente,
                creado=False
            )

            db.rollback()
            return resultado

        if obligacion.estado != "ACTIVA":
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle="La obligación no está activa"
            )

        # Bloqueo de la cuenta del abono.
        cuenta = bloquear_cuenta_obligacion(
            db,
            datos.id_cuenta,
            id_usuario
        )

        if cuenta is None:
            raise ErrorNegocio(
                codigo=CodigoError.NO_ENCONTRADO,
                detalle="Cuenta no encontrada"
            )

        if cuenta.estado != "ACTIVA":
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle="La cuenta está inactiva"
            )

        # Revisar nuevamente la idempotencia.
        existente = buscar_movimiento_obligacion_uuid(
            db,
            datos.uuid_local
        )

        if existente is not None:
            if not misma_operacion(
                existente,
                datos,
                tipo
            ):
                raise ErrorNegocio(
                    codigo=CodigoError.CONFLICTO,
                    detalle="UUID utilizado por otra operación"
                )

            pendiente = calcular_pendiente(
                db,
                obligacion
            )

            resultado = respuesta_abono(
                existente,
                obligacion,
                pendiente,
                creado=False
            )

            db.rollback()
            return resultado

        pendiente_actual = calcular_pendiente(
            db,
            obligacion
        )

        if pendiente_actual <= CERO:
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle="La obligación ya está saldada"
            )

        if datos.monto > pendiente_actual:
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle="El abono supera el monto pendiente"
            )

        # POR_PAGAR: el pago sale de la cuenta.
        # POR_COBRAR: el cobro entra a la cuenta.
        if tipo == "GASTO":
            exigir_saldo_libre(
                db,
                cuenta,
                datos.monto
            )

        movimiento = Movimiento(
            uuid_local=datos.uuid_local,
            id_cuenta=datos.id_cuenta,
            id_categoria=None,
            id_transferencia=None,
            id_obligacion=obligacion.id_obligacion,
            tipo=tipo,
            origen="OBLIGACION",
            monto=datos.monto,
            fecha_movimiento=datos.fecha_movimiento,
            descripcion=datos.descripcion,
            aplica_gmf=False,
            monto_gmf=CERO,
            estado="ACTIVO",
        )

        agregar_movimiento_obligacion(
            db,
            movimiento
        )

        nuevo_pendiente = (
            pendiente_actual - datos.monto
        )

        if nuevo_pendiente == CERO:
            obligacion.estado = "SALDADA"

        resultado = respuesta_abono(
            movimiento,
            obligacion,
            nuevo_pendiente,
            creado=True
        )

        db.commit()
        return resultado

    except IntegrityError:
        db.rollback()

        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "Conflicto de integridad al registrar "
                "el abono"
            )
        )

    except Exception:
        db.rollback()
        raise