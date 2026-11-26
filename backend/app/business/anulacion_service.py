
from decimal import Decimal

from app.persistence.unidad_trabajo_repository import refrescar_entidad
from app.business.errores import CodigoError, ErrorNegocio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Movimiento,
)

from app.persistence.anulacion_repository import (
    consultar_movimiento_usuario,
    consultar_transferencia,
    bloquear_movimiento_usuario,
    bloquear_movimientos_transferencia,
    bloquear_transferencia,
    bloquear_obligacion_anulacion,
)

from app.persistence.movimiento_escritura_repository import (
    bloquear_cuenta,
)

from app.persistence.transferencia_repository import (
    bloquear_cuentas_usuario,
)

from app.persistence.obligacion_escritura_repository import (
    obtener_abonos_obligacion,
)

from app.business.saldo_libre_service import (
    exigir_saldo_libre,
)


CERO = Decimal("0.00")


def tipo_abono_obligacion(obligacion):
    if obligacion.tipo_obligacion == "POR_PAGAR":
        return "GASTO"

    if obligacion.tipo_obligacion == "POR_COBRAR":
        return "INGRESO"

    raise ErrorNegocio(
        codigo=CodigoError.CONFLICTO,
        detalle="Tipo de obligación no válido"
    )


def recalcular_estado_obligacion(
    db: Session,
    obligacion
):
    tipo = tipo_abono_obligacion(
        obligacion
    )

    movimientos = obtener_abonos_obligacion(
        db,
        obligacion.id_obligacion,
        tipo
    )

    abonado = sum(
        (
            m.monto
            for m in movimientos
            if m.estado == "ACTIVO"
        ),
        CERO
    )

    pendiente = obligacion.monto_original - abonado

    obligacion.estado = (
        "SALDADA"
        if pendiente <= CERO
        else "ACTIVA"
    )





def _bloquear_cuenta_y_movimiento(
    db: Session,
    id_usuario: int,
    id_movimiento: int,
    id_cuenta: int
):
    """
    Bloqueo consistente para una operación
    que afecta a una sola cuenta.
    """
    cuenta = bloquear_cuenta(
        db,
        id_cuenta,
        id_usuario
    )

    if cuenta is None:
        raise ErrorNegocio(
            codigo=CodigoError.NO_ENCONTRADO,
            detalle="Cuenta no encontrada"
        )

    movimiento = bloquear_movimiento_usuario(
        db,
        id_movimiento,
        id_usuario
    )

    if movimiento is None:
        raise ErrorNegocio(
            codigo=CodigoError.NO_ENCONTRADO,
            detalle="Movimiento no encontrado"
        )

    refrescar_entidad(db, movimiento)

    if movimiento.id_cuenta != cuenta.id_cuenta:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="La cuenta del movimiento cambió"
        )

    if movimiento.estado != "ACTIVO":
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="El movimiento ya está anulado"
        )

    return cuenta, movimiento


def _anular_normal(
    db: Session,
    id_usuario: int,
    vista: Movimiento
):
    cuenta, movimiento = (
        _bloquear_cuenta_y_movimiento(
            db,
            id_usuario,
            vista.id_movimiento,
            vista.id_cuenta
        )
    )

    if movimiento.origen != "NORMAL":
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Origen inconsistente"
        )

    # Anular un ingreso elimina dinero
    # que anteriormente entró a la cuenta.
    if movimiento.tipo == "INGRESO":
        exigir_saldo_libre(
            db,
            cuenta,
            movimiento.monto
        )

    movimiento.estado = "ANULADO"

    db.commit()

    return {
        "id_movimiento": movimiento.id_movimiento,
        "estado": "ANULADO",
        "mensaje": (
            "Movimiento normal anulado correctamente"
        ),
    }


def _anular_transferencia(
    db: Session,
    id_usuario: int,
    vista: Movimiento
):
    if vista.id_transferencia is None:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Transferencia inconsistente"
        )

    # Se consultan los IDs antes de bloquear
    # para obtener luego ambas cuentas
    # en orden ascendente.
    transferencia_vista = consultar_transferencia(db, vista.id_transferencia)

    if transferencia_vista is None:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Transferencia no encontrada"
        )

    cuentas = bloquear_cuentas_usuario(
        db,
        id_usuario,
        transferencia_vista.id_cuenta_origen,
        transferencia_vista.id_cuenta_destino
    )

    if len(cuentas) != 2:
        raise ErrorNegocio(
            codigo=CodigoError.NO_ENCONTRADO,
            detalle="Transferencia no encontrada"
        )

    transferencia = bloquear_transferencia(
        db,
        vista.id_transferencia
    )

    if transferencia is None:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Transferencia no encontrada"
        )

    refrescar_entidad(db, transferencia)

    if transferencia.estado != "ACTIVA":
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="La transferencia ya fue anulada"
        )

    movimientos = bloquear_movimientos_transferencia(
        db,
        transferencia.id_transferencia
    )

    if len(movimientos) != 2:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "La transferencia no tiene "
                "los dos movimientos esperados"
            )
        )

    for movimiento in movimientos:
        refrescar_entidad(db, movimiento)

        if (
            movimiento.estado != "ACTIVO"
            or movimiento.origen != "TRANSFERENCIA"
        ):
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle="Movimientos de transferencia inconsistentes"
            )

    salidas = [
        m for m in movimientos
        if (
            m.tipo == "GASTO"
            and m.id_cuenta
                == transferencia.id_cuenta_origen
        )
    ]

    entradas = [
        m for m in movimientos
        if (
            m.tipo == "INGRESO"
            and m.id_cuenta
                == transferencia.id_cuenta_destino
        )
    ]

    if len(salidas) != 1 or len(entradas) != 1:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Direcciones de transferencia inconsistentes"
        )

    if vista.id_movimiento not in {
        m.id_movimiento for m in movimientos
    }:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="El movimiento no pertenece a la transferencia"
        )

    # Anular la transferencia retira el
    # dinero que había entrado al destino.
    # No se puede retirar si ya fue reservado.
    destino = cuentas[
        transferencia.id_cuenta_destino
    ]

    exigir_saldo_libre(
        db,
        destino,
        entradas[0].monto
    )

    for movimiento in movimientos:
        movimiento.estado = "ANULADO"

    transferencia.estado = "ANULADA"

    db.commit()

    return {
        "id_movimiento": vista.id_movimiento,
        "estado": "ANULADO",
        "mensaje": (
            "Transferencia anulada correctamente"
        ),
    }


def _anular_abono_obligacion(
    db: Session,
    id_usuario: int,
    vista: Movimiento
):
    if vista.id_obligacion is None:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Movimiento de obligación inconsistente"
        )

    # Mismo orden que el registro de abonos:
    # obligación -> cuenta -> movimiento.
    obligacion = bloquear_obligacion_anulacion(
        db,
        vista.id_obligacion
    )

    if (
        obligacion is None
        or obligacion.id_usuario != id_usuario
    ):
        raise ErrorNegocio(
            codigo=CodigoError.NO_ENCONTRADO,
            detalle="Obligación no encontrada"
        )

    cuenta, movimiento = (
        _bloquear_cuenta_y_movimiento(
            db,
            id_usuario,
            vista.id_movimiento,
            vista.id_cuenta
        )
    )

    if (
        movimiento.origen != "OBLIGACION"
        or movimiento.id_obligacion
            != obligacion.id_obligacion
    ):
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Movimiento de obligación inconsistente"
        )

    tipo_abono = tipo_abono_obligacion(
        obligacion
    )

    # El capital inicial y los abonos tienen
    # sentidos opuestos. El capital inicial
    # nunca se anula aisladamente.
    if movimiento.tipo != tipo_abono:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "El movimiento inicial de una "
                "obligación no puede anularse "
                "por separado"
            )
        )

    # Si anulamos un cobro POR_COBRAR,
    # estamos retirando dinero ingresado.
    if movimiento.tipo == "INGRESO":
        exigir_saldo_libre(
            db,
            cuenta,
            movimiento.monto
        )

    movimiento.estado = "ANULADO"

    db.flush()

    recalcular_estado_obligacion(
        db,
        obligacion
    )

    db.commit()

    return {
        "id_movimiento": movimiento.id_movimiento,
        "estado": "ANULADO",
        "mensaje": (
            "Abono de obligación anulado correctamente"
        ),
    }


def anular_movimiento(
    db: Session,
    id_usuario: int,
    id_movimiento: int
):
    if id_usuario <= 0:
        raise ErrorNegocio(
            codigo=CodigoError.NO_AUTENTICADO,
            detalle="Usuario no válido"
        )

    try:
        vista = consultar_movimiento_usuario(
            db,
            id_usuario,
            id_movimiento
        )

        if vista is None:
            raise ErrorNegocio(
                codigo=CodigoError.NO_ENCONTRADO,
                detalle="Movimiento no encontrado"
            )

        if vista.origen == "NORMAL":
            return _anular_normal(
                db,
                id_usuario,
                vista
            )

        if vista.origen == "TRANSFERENCIA":
            return _anular_transferencia(
                db,
                id_usuario,
                vista
            )

        if vista.origen == "OBLIGACION":
            return _anular_abono_obligacion(
                db,
                id_usuario,
                vista
            )

        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Origen de movimiento no válido"
        )

    except IntegrityError:
        db.rollback()

        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Conflicto de integridad al anular"
        )

    except Exception:
        db.rollback()
        raise
