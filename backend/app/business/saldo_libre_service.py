
from decimal import Decimal

from app.business.errores import CodigoError, ErrorNegocio
from sqlalchemy.orm import Session

from app.persistence.movimiento_escritura_repository import (
    calcular_saldo_cuenta,
)

from app.persistence.meta_reserva_repository import (
    reservado_por_cuenta,
)


CERO = Decimal("0.00")


def consultar_disponibilidad_cuenta(
    db: Session,
    cuenta
):
    """
    Debe llamarse después de bloquear
    la fila de la cuenta con FOR UPDATE
    si se utilizará para autorizar una escritura.

    No altera ningún saldo.
    """
    saldo_real = Decimal(
        calcular_saldo_cuenta(db, cuenta)
    )

    reservado = Decimal(
        reservado_por_cuenta(
            db,
            cuenta.id_usuario,
            cuenta.id_cuenta
        )
    )

    saldo_libre = saldo_real - reservado

    return {
        "saldo_real": saldo_real,
        "monto_reservado": reservado,
        "saldo_libre": saldo_libre,
    }


def exigir_saldo_libre(
    db: Session,
    cuenta,
    importe: Decimal
):
    """
    Valida una salida de dinero.

    La cuenta debe estar bloqueada en la
    misma transacción que registrará
    el movimiento.
    """
    importe = Decimal(importe)

    if importe <= CERO:
        raise ErrorNegocio(
            codigo=CodigoError.VALIDACION,
            detalle="El importe debe ser positivo"
        )

    if cuenta.estado != "ACTIVA":
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="La cuenta está inactiva"
        )

    disponibilidad = consultar_disponibilidad_cuenta(
        db,
        cuenta
    )

    if disponibilidad["monto_reservado"] < CERO:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "La cuenta tiene reservas inconsistentes. "
                "Es necesaria una revisión financiera"
            )
        )

    if disponibilidad["saldo_libre"] < importe:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "Saldo libre insuficiente. "
                "Saldo real: "
                f"{disponibilidad['saldo_real']:.2f}; "
                "reservado: "
                f"{disponibilidad['monto_reservado']:.2f}; "
                "libre: "
                f"{disponibilidad['saldo_libre']:.2f}; "
                "operación: "
                f"{importe:.2f}. "
                "Puedes liberar ahorro desde Metas "
                "antes de volver a intentarlo"
            )
        )

    return disponibilidad
