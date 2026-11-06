from decimal import Decimal, ROUND_HALF_UP
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Movimiento, Transferencia

from app.persistence.movimiento_escritura_repository import (
    calcular_saldo_cuenta,
)

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


TASA_GMF = Decimal("0.004")


def generar_uuids_transferencia(
    uuid_operacion: UUID
):
    uuid_salida = uuid5(
        NAMESPACE_URL,
        f"{uuid_operacion}:salida"
    )

    uuid_entrada = uuid5(
        NAMESPACE_URL,
        f"{uuid_operacion}:entrada"
    )

    return uuid_salida, uuid_entrada


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
    movimiento_salida: Movimiento,
    movimiento_entrada: Movimiento,
    monto_gmf: Decimal,
) -> bool:

    return (
        transferencia.id_cuenta_origen
        == datos.id_cuenta_origen

        and transferencia.id_cuenta_destino
        == datos.id_cuenta_destino

        and transferencia.monto
        == datos.monto

        and transferencia.fecha_transferencia
        == datos.fecha_transferencia

        and transferencia.motivo
        == datos.motivo

        and transferencia.estado
        == "ACTIVA"

        and movimiento_salida.tipo
        == "GASTO"

        and movimiento_salida.origen
        == "TRANSFERENCIA"

        and movimiento_salida.monto
        == datos.monto

        and movimiento_salida.monto_gmf
        == monto_gmf

        and movimiento_entrada.tipo
        == "INGRESO"

        and movimiento_entrada.origen
        == "TRANSFERENCIA"

        and movimiento_entrada.monto
        == datos.monto

        and movimiento_entrada.monto_gmf
        == Decimal("0.00")
    )


def respuesta_transferencia(
    transferencia: Transferencia,
    uuid_operacion: UUID,
    salida: Movimiento,
    entrada: Movimiento,
    creado: bool,
):
    return {
        "id_transferencia":
            transferencia.id_transferencia,

        "uuid_operacion":
            uuid_operacion,

        "id_movimiento_salida":
            salida.id_movimiento,

        "id_movimiento_entrada":
            entrada.id_movimiento,

        "monto":
            transferencia.monto,

        "monto_gmf":
            salida.monto_gmf,

        "creado":
            creado,

        "mensaje": (
            "Transferencia registrada correctamente"
            if creado
            else
            "Transferencia previamente registrada"
        )
    }


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

        # ---------------------------------
        # 1. Comprobar posible reintento
        # ---------------------------------

        salida_existente = buscar_movimiento_por_uuid(
            db,
            uuid_salida
        )

        entrada_existente = buscar_movimiento_por_uuid(
            db,
            uuid_entrada
        )

        if (
            salida_existente is not None
            or entrada_existente is not None
        ):
            # La operación atómica debería haber
            # creado ambos o ninguno.
            if (
                salida_existente is None
                or entrada_existente is None
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "La transferencia existente "
                        "presenta una inconsistencia"
                    )
                )

            if (
                salida_existente.id_transferencia
                != entrada_existente.id_transferencia
            ):
                raise HTTPException(
                    status_code=409,
                    detail="UUID utilizado por otra operación"
                )

            transferencia_existente = buscar_transferencia(
                db,
                salida_existente.id_transferencia
            )

            if transferencia_existente is None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Transferencia relacionada no encontrada"
                    )
                )

            # Verificar que pertenezca al usuario.
            cuentas = bloquear_cuentas_usuario(
                db,
                id_usuario,
                transferencia_existente.id_cuenta_origen,
                transferencia_existente.id_cuenta_destino
            )

            if len(cuentas) != 2:
                raise HTTPException(
                    status_code=404,
                    detail="Transferencia no encontrada"
                )

            if not misma_transferencia(
                transferencia_existente,
                datos,
                salida_existente,
                entrada_existente,
                monto_gmf
            ):
                raise HTTPException(
                    status_code=409,
                    detail="UUID utilizado por otra operación"
                )

            resultado = respuesta_transferencia(
                transferencia_existente,
                datos.uuid_operacion,
                salida_existente,
                entrada_existente,
                creado=False
            )

            db.rollback()

            return resultado

        # ---------------------------------
        # 2. Bloquear ambas cuentas
        # ---------------------------------

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

        cuenta_origen = cuentas[
            datos.id_cuenta_origen
        ]

        cuenta_destino = cuentas[
            datos.id_cuenta_destino
        ]

        if (
            cuenta_origen.estado != "ACTIVA"
            or cuenta_destino.estado != "ACTIVA"
        ):
            raise HTTPException(
                status_code=409,
                detail="Ambas cuentas deben estar activas"
            )

        # ---------------------------------
        # 3. Verificar UUID nuevamente
        #    después de adquirir locks
        # ---------------------------------

        salida_existente = buscar_movimiento_por_uuid(
            db,
            uuid_salida
        )

        entrada_existente = buscar_movimiento_por_uuid(
            db,
            uuid_entrada
        )

        if (
            salida_existente is not None
            or entrada_existente is not None
        ):
            raise HTTPException(
                status_code=409,
                detail="La operación ya fue procesada"
            )

        # ---------------------------------
        # 4. Fondos disponibles
        # ---------------------------------

        saldo_origen = calcular_saldo_cuenta(
            db,
            cuenta_origen
        )

        total_debito = (
            datos.monto + monto_gmf
        )

        if saldo_origen < total_debito:
            raise HTTPException(
                status_code=409,
                detail="Saldo insuficiente"
            )

        # ---------------------------------
        # 5. Crear transferencia
        # ---------------------------------

        transferencia = Transferencia(
            id_cuenta_origen=
                datos.id_cuenta_origen,

            id_cuenta_destino=
                datos.id_cuenta_destino,

            monto=datos.monto,

            fecha_transferencia=
                datos.fecha_transferencia,

            motivo=datos.motivo,

            estado="ACTIVA"
        )

        agregar_transferencia(
            db,
            transferencia
        )

        # ---------------------------------
        # 6. Movimiento de salida
        # ---------------------------------

        salida = Movimiento(
            uuid_local=uuid_salida,

            id_cuenta=
                datos.id_cuenta_origen,

            id_categoria=None,

            id_transferencia=
                transferencia.id_transferencia,

            id_obligacion=None,

            tipo="GASTO",

            origen="TRANSFERENCIA",

            monto=datos.monto,

            fecha_movimiento=
                datos.fecha_transferencia,

            descripcion=datos.motivo,

            aplica_gmf=
                datos.aplica_gmf,

            monto_gmf=monto_gmf,

            estado="ACTIVO"
        )

        agregar_movimiento_transferencia(
            db,
            salida
        )

        # ---------------------------------
        # 7. Movimiento de entrada
        # ---------------------------------

        entrada = Movimiento(
            uuid_local=uuid_entrada,

            id_cuenta=
                datos.id_cuenta_destino,

            id_categoria=None,

            id_transferencia=
                transferencia.id_transferencia,

            id_obligacion=None,

            tipo="INGRESO",

            origen="TRANSFERENCIA",

            monto=datos.monto,

            fecha_movimiento=
                datos.fecha_transferencia,

            descripcion=datos.motivo,

            aplica_gmf=False,

            monto_gmf=Decimal("0.00"),

            estado="ACTIVO"
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

        # Los tres registros se confirman juntos.
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
                "al registrar la transferencia"
            )
        )

    except Exception:
        db.rollback()
        raise