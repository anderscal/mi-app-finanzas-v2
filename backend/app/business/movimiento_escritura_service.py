
from decimal import Decimal, ROUND_HALF_UP

from app.business.errores import CodigoError, ErrorNegocio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Movimiento

from app.schemas.movimiento_schema import (
    MovimientoNormalCrear,
)

from app.persistence.movimiento_escritura_repository import (
    agregar_movimiento,
    bloquear_cuenta,
    buscar_categoria,
    buscar_movimiento_uuid,
)

from app.business.saldo_libre_service import (
    exigir_saldo_libre,
)


TASA_GMF = Decimal("0.004")
CERO = Decimal("0.00")


def calcular_gmf_normal(
    datos: MovimientoNormalCrear
) -> Decimal:
    if datos.tipo != "GASTO" or not datos.aplica_gmf:
        return CERO

    return (
        datos.monto * TASA_GMF
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def misma_solicitud(
    movimiento: Movimiento,
    datos: MovimientoNormalCrear,
) -> bool:
    return (
        movimiento.id_cuenta == datos.id_cuenta
        and movimiento.id_categoria == datos.id_categoria
        and movimiento.tipo == datos.tipo
        and movimiento.origen == "NORMAL"
        and movimiento.monto == datos.monto
        and movimiento.fecha_movimiento == datos.fecha_movimiento
        and movimiento.descripcion == datos.descripcion
        and movimiento.aplica_gmf == datos.aplica_gmf
        and movimiento.monto_gmf == calcular_gmf_normal(datos)
    )


def respuesta_movimiento(
    movimiento: Movimiento,
    creado: bool
):
    return {
        "id_movimiento": movimiento.id_movimiento,
        "uuid_local": movimiento.uuid_local,
        "tipo": movimiento.tipo,
        "monto": movimiento.monto,
        "aplica_gmf": movimiento.aplica_gmf,
        "monto_gmf": movimiento.monto_gmf,
        "creado": creado,
        "mensaje": (
            "Movimiento registrado correctamente"
            if creado
            else "Movimiento previamente registrado"
        ),
    }


def _validar_reintento(
    db: Session,
    id_usuario: int,
    datos: MovimientoNormalCrear,
):
    existente = buscar_movimiento_uuid(
        db,
        datos.uuid_local
    )

    if existente is None:
        return None

    if not misma_solicitud(existente, datos):
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="UUID utilizado por otra operación",
        )

    cuenta = bloquear_cuenta(
        db,
        existente.id_cuenta,
        id_usuario
    )

    if cuenta is None:
        raise ErrorNegocio(
            codigo=CodigoError.NO_ENCONTRADO,
            detalle="Movimiento no encontrado",
        )

    if existente.estado != "ACTIVO":
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="La operación ya no está activa",
        )

    return respuesta_movimiento(
        existente,
        creado=False
    )


def registrar_movimiento_normal(
    db: Session,
    id_usuario: int,
    datos: MovimientoNormalCrear,
):
    if id_usuario <= 0:
        raise ErrorNegocio(
            codigo=CodigoError.NO_AUTENTICADO,
            detalle="Usuario no válido",
        )

    try:
        # 1. Si el UUID ya se confirmó,
        # no volver a descontar el GMF.
        resultado = _validar_reintento(
            db,
            id_usuario,
            datos
        )

        if resultado is not None:
            db.rollback()
            return resultado

        # 2. Bloquear la cuenta para
        # validar el saldo y las reservas.
        cuenta = bloquear_cuenta(
            db,
            datos.id_cuenta,
            id_usuario
        )

        if cuenta is None:
            raise ErrorNegocio(
                codigo=CodigoError.NO_ENCONTRADO,
                detalle="Cuenta no encontrada",
            )

        if cuenta.estado != "ACTIVA":
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle="La cuenta está inactiva",
            )

        # 3. Reconocer una operación que
        # finalizó mientras se esperaba el bloqueo.
        resultado = _validar_reintento(
            db,
            id_usuario,
            datos
        )

        if resultado is not None:
            db.rollback()
            return resultado

        # 4. Validar la categoría.
        categoria = buscar_categoria(
            db,
            datos.id_categoria
        )

        if categoria is None:
            raise ErrorNegocio(
                codigo=CodigoError.NO_ENCONTRADO,
                detalle="Categoría no encontrada",
            )

        if categoria.estado != "ACTIVA":
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle="Categoría inactiva",
            )

        if categoria.tipo_categoria != datos.tipo:
            raise ErrorNegocio(
                codigo=CodigoError.VALIDACION,
                detalle=(
                    "La categoría no corresponde "
                    "al tipo de movimiento"
                ),
            )

        if not (
            categoria.es_sistema
            or categoria.id_usuario == id_usuario
        ):
            raise ErrorNegocio(
                codigo=CodigoError.PROHIBIDO,
                detalle="Categoría no autorizada",
            )

        # 5. Calcular GMF en el backend.
        monto_gmf = calcular_gmf_normal(datos)

        if datos.tipo == "GASTO":
            # NUEVA REGLA:
            # el dinero libre debe cubrir
            # el gasto y el impuesto.
            exigir_saldo_libre(
                db,
                cuenta,
                datos.monto + monto_gmf
            )

        # 6. Crear el movimiento con GMF.
        nuevo = Movimiento(
            uuid_local=datos.uuid_local,
            id_cuenta=datos.id_cuenta,
            id_categoria=datos.id_categoria,
            id_transferencia=None,
            id_obligacion=None,
            tipo=datos.tipo,
            origen="NORMAL",
            monto=datos.monto,
            fecha_movimiento=datos.fecha_movimiento,
            descripcion=datos.descripcion,
            aplica_gmf=datos.aplica_gmf,
            monto_gmf=monto_gmf,
            estado="ACTIVO",
        )

        agregar_movimiento(
            db,
            nuevo
        )

        resultado = respuesta_movimiento(
            nuevo,
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
                "el movimiento"
            ),
        )

    except Exception:
        db.rollback()
        raise
