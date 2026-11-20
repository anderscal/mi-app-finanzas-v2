
from fastapi import HTTPException
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


def misma_solicitud(
    movimiento: Movimiento,
    datos: MovimientoNormalCrear
) -> bool:
    return (
        movimiento.id_cuenta == datos.id_cuenta
        and movimiento.id_categoria == datos.id_categoria
        and movimiento.tipo == datos.tipo
        and movimiento.origen == "NORMAL"
        and movimiento.monto == datos.monto
        and movimiento.fecha_movimiento == datos.fecha_movimiento
        and movimiento.descripcion == datos.descripcion
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
    datos: MovimientoNormalCrear
):
    existente = buscar_movimiento_uuid(
        db,
        datos.uuid_local
    )

    if existente is None:
        return None

    if not misma_solicitud(existente, datos):
        raise HTTPException(
            status_code=409,
            detail="UUID utilizado por otra operación"
        )

    cuenta = bloquear_cuenta(
        db,
        existente.id_cuenta,
        id_usuario
    )

    if cuenta is None:
        raise HTTPException(
            status_code=404,
            detail="Movimiento no encontrado"
        )

    if existente.estado != "ACTIVO":
        raise HTTPException(
            status_code=409,
            detail="La operación ya no está activa"
        )

    return respuesta_movimiento(
        existente,
        creado=False
    )


def registrar_movimiento_normal(
    db: Session,
    id_usuario: int,
    datos: MovimientoNormalCrear
):
    if id_usuario <= 0:
        raise HTTPException(
            status_code=401,
            detail="Usuario no válido"
        )

    try:
        # Primero reconocer un movimiento confirmado.
        resultado = _validar_reintento(
            db,
            id_usuario,
            datos
        )

        if resultado is not None:
            db.rollback()
            return resultado

        # Serializar escrituras sobre la cuenta.
        cuenta = bloquear_cuenta(
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

        # Otro intento pudo confirmar el UUID
        # mientras esperábamos el bloqueo.
        resultado = _validar_reintento(
            db,
            id_usuario,
            datos
        )

        if resultado is not None:
            db.rollback()
            return resultado

        categoria = buscar_categoria(
            db,
            datos.id_categoria
        )

        if categoria is None:
            raise HTTPException(
                status_code=404,
                detail="Categoría no encontrada"
            )

        if categoria.estado != "ACTIVA":
            raise HTTPException(
                status_code=409,
                detail="Categoría inactiva"
            )

        if categoria.tipo_categoria != datos.tipo:
            raise HTTPException(
                status_code=422,
                detail=(
                    "La categoría no corresponde "
                    "al tipo de movimiento"
                )
            )

        if not (
            categoria.es_sistema
            or categoria.id_usuario == id_usuario
        ):
            raise HTTPException(
                status_code=403,
                detail="Categoría no autorizada"
            )

        # NUEVA REGLA: un gasto solo puede
        # consumir dinero no reservado.
        if datos.tipo == "GASTO":
            exigir_saldo_libre(
                db,
                cuenta,
                datos.monto
            )

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
            aplica_gmf=False,
            monto_gmf=0,
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
        raise HTTPException(
            status_code=409,
            detail=(
                "Conflicto de integridad al registrar "
                "el movimiento"
            )
        )

    except Exception:
        db.rollback()
        raise
