
from decimal import Decimal, ROUND_HALF_UP
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Movimiento, Transferencia

from app.persistence.transferencia_repository import (
    agregar_movimiento_transferencia,
    agregar_transferencia,
    bloquear_cuentas_usuario,
    buscar_movimiento_por_uuid,
    buscar_transferencia,
)

from app.schemas.movimiento_schema import (
    TransferenciaCrear,
)

from app.business.saldo_libre_service import (
    exigir_saldo_libre,
)


TASA_GMF = Decimal("0.004")


def generar_uuids_transferencia(
    uuid_operacion: UUID
):
    return (
        uuid5(
            NAMESPACE_URL,
            f"{uuid_operacion}:salida"
        ),
        uuid5(
            NAMESPACE_URL,
            f"{uuid_operacion}:entrada"
        ),
    )


def calcular_gmf(
    monto: Decimal,
    aplica_gmf: bool
) -> Decimal:
    if not aplica_gmf:
        return Decimal("0.00")

    return (
        monto * TASA_GMF
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def misma_transferencia(
    transferencia: Transferencia,
    datos: TransferenciaCrear,
    salida: Movimiento,
    entrada: Movimiento,
    monto_gmf: Decimal
) -> bool:
    return (
        transferencia.id_cuenta_origen
            == datos.id_cuenta_origen
        and transferencia.id_cuenta_destino
            == datos.id_cuenta_destino
        and transferencia.monto == datos.monto
        and transferencia.fecha_transferencia
            == datos.fecha_transferencia
        and transferencia.motivo == datos.motivo
        and transferencia.estado == "ACTIVA"
        and salida.id_transferencia
            == transferencia.id_transferencia
        and entrada.id_transferencia
            == transferencia.id_transferencia
        and salida.id_cuenta
            == datos.id_cuenta_origen
        and entrada.id_cuenta
            == datos.id_cuenta_destino
        and salida.tipo == "GASTO"
        and entrada.tipo == "INGRESO"
        and salida.origen == "TRANSFERENCIA"
        and entrada.origen == "TRANSFERENCIA"
        and salida.estado == "ACTIVO"
        and entrada.estado == "ACTIVO"
        and salida.monto == datos.monto
        and entrada.monto == datos.monto
        and salida.aplica_gmf == datos.aplica_gmf
        and salida.monto_gmf == monto_gmf
        and entrada.monto_gmf == Decimal("0.00")
    )


def respuesta_transferencia(
    transferencia: Transferencia,
    uuid_operacion: UUID,
    salida: Movimiento,
    entrada: Movimiento,
    creado: bool
):
    return {
        "id_transferencia": transferencia.id_transferencia,
        "uuid_operacion": uuid_operacion,
        "id_movimiento_salida": salida.id_movimiento,
        "id_movimiento_entrada": entrada.id_movimiento,
        "monto": transferencia.monto,
        "monto_gmf": salida.monto_gmf,
        "creado": creado,
        "mensaje": (
            "Transferencia registrada correctamente"
            if creado
            else "Transferencia previamente registrada"
        ),
    }


def _consultar_reintento(
    db: Session,
    id_usuario: int,
    datos: TransferenciaCrear,
    uuid_salida: UUID,
    uuid_entrada: UUID,
    monto_gmf: Decimal
):
    salida = buscar_movimiento_por_uuid(
        db,
        uuid_salida
    )

    entrada = buscar_movimiento_por_uuid(
        db,
        uuid_entrada
    )

    if salida is None and entrada is None:
        return None

    if salida is None or entrada is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "La transferencia presenta "
                "movimientos inconsistentes"
            )
        )

    if (
        salida.id_transferencia is None
        or salida.id_transferencia
            != entrada.id_transferencia
    ):
        raise HTTPException(
            status_code=409,
            detail="UUID utilizado por otra operación"
        )

    transferencia = buscar_transferencia(
        db,
        salida.id_transferencia
    )

    if transferencia is None:
        raise HTTPException(
            status_code=409,
            detail="Transferencia relacionada no encontrada"
        )

    cuentas = bloquear_cuentas_usuario(
        db,
        id_usuario,
        transferencia.id_cuenta_origen,
        transferencia.id_cuenta_destino
    )

    if len(cuentas) != 2:
        raise HTTPException(
            status_code=404,
            detail="Transferencia no encontrada"
        )

    if not misma_transferencia(
        transferencia,
        datos,
        salida,
        entrada,
        monto_gmf
    ):
        raise HTTPException(
            status_code=409,
            detail="UUID utilizado por otra operación"
        )

    return respuesta_transferencia(
        transferencia,
        datos.uuid_operacion,
        salida,
        entrada,
        creado=False
    )


def registrar_transferencia(
    db: Session,
    id_usuario: int,
    datos: TransferenciaCrear
):
    if id_usuario <= 0:
        raise HTTPException(
            status_code=401,
            detail="Usuario no válido"
        )

    if datos.id_cuenta_origen == datos.id_cuenta_destino:
        raise HTTPException(
            status_code=422,
            detail="Las cuentas deben ser diferentes"
        )

    uuid_salida, uuid_entrada = (
        generar_uuids_transferencia(
            datos.uuid_operacion
        )
    )

    monto_gmf = calcular_gmf(
        datos.monto,
        datos.aplica_gmf
    )

    try:
        # Idempotencia antes de crear.
        resultado = _consultar_reintento(
            db,
            id_usuario,
            datos,
            uuid_salida,
            uuid_entrada,
            monto_gmf
        )

        if resultado is not None:
            db.rollback()
            return resultado

        # Bloqueo ordenado de ambas cuentas.
        cuentas = bloquear_cuentas_usuario(
            db,
            id_usuario,
            datos.id_cuenta_origen,
            datos.id_cuenta_destino
        )

        if len(cuentas) != 2:
            raise HTTPException(
                status_code=404,
                detail="Una o ambas cuentas no existen"
            )

        origen = cuentas[datos.id_cuenta_origen]
        destino = cuentas[datos.id_cuenta_destino]

        if (
            origen.estado != "ACTIVA"
            or destino.estado != "ACTIVA"
        ):
            raise HTTPException(
                status_code=409,
                detail="Ambas cuentas deben estar activas"
            )

        # Reintento tras esperar los bloqueos.
        resultado = _consultar_reintento(
            db,
            id_usuario,
            datos,
            uuid_salida,
            uuid_entrada,
            monto_gmf
        )

        if resultado is not None:
            db.rollback()
            return resultado

        total_debito = datos.monto + monto_gmf

        # NUEVA REGLA: las reservas del origen
        # no pueden financiar una transferencia.
        exigir_saldo_libre(
            db,
            origen,
            total_debito
        )

        transferencia = Transferencia(
            id_cuenta_origen=datos.id_cuenta_origen,
            id_cuenta_destino=datos.id_cuenta_destino,
            monto=datos.monto,
            fecha_transferencia=datos.fecha_transferencia,
            motivo=datos.motivo,
            estado="ACTIVA",
        )

        agregar_transferencia(
            db,
            transferencia
        )

        salida = Movimiento(
            uuid_local=uuid_salida,
            id_cuenta=datos.id_cuenta_origen,
            id_categoria=None,
            id_transferencia=transferencia.id_transferencia,
            id_obligacion=None,
            tipo="GASTO",
            origen="TRANSFERENCIA",
            monto=datos.monto,
            fecha_movimiento=datos.fecha_transferencia,
            descripcion=datos.motivo,
            aplica_gmf=datos.aplica_gmf,
            monto_gmf=monto_gmf,
            estado="ACTIVO",
        )

        agregar_movimiento_transferencia(
            db,
            salida
        )

        entrada = Movimiento(
            uuid_local=uuid_entrada,
            id_cuenta=datos.id_cuenta_destino,
            id_categoria=None,
            id_transferencia=transferencia.id_transferencia,
            id_obligacion=None,
            tipo="INGRESO",
            origen="TRANSFERENCIA",
            monto=datos.monto,
            fecha_movimiento=datos.fecha_transferencia,
            descripcion=datos.motivo,
            aplica_gmf=False,
            monto_gmf=Decimal("0.00"),
            estado="ACTIVO",
        )

        agregar_movimiento_transferencia(
            db,
            entrada
        )

        resultado = respuesta_transferencia(
            transferencia,
            datos.uuid_operacion,
            salida,
            entrada,
            creado=True
        )

        db.commit()
        return resultado

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Conflicto de integridad al registrar "
                "la transferencia"
            )
        )

    except Exception:
        db.rollback()
        raise
