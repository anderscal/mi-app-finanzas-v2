
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Movimiento
from app.schemas.movimiento_schema import MovimientoNormalCrear

from app.persistence.movimiento_escritura_repository import (
    agregar_movimiento,
    bloquear_cuenta,
    buscar_categoria,
    buscar_movimiento_uuid,
    calcular_saldo_cuenta,
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
        )
    }


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
        # 1. Revisar si la operación ya existe.
        existente = buscar_movimiento_uuid(
            db, datos.uuid_local
        )

        if existente is not None:
            if not misma_solicitud(existente, datos):
                raise HTTPException(
                    status_code=409,
                    detail="UUID utilizado por otra operación"
                )

            cuenta_existente = bloquear_cuenta(
                db, existente.id_cuenta, id_usuario
            )

            if cuenta_existente is None:
                raise HTTPException(
                    status_code=404,
                    detail="Movimiento no encontrado"
                )

            if existente.estado != "ACTIVO":
                raise HTTPException(
                    status_code=409,
                    detail="La operación ya no está activa"
                )

            resultado = respuesta_movimiento(
                existente, creado=False
            )

            db.rollback()
            return resultado

        # 2. Bloquear la cuenta del usuario.
        cuenta = bloquear_cuenta(
            db, datos.id_cuenta, id_usuario
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

        # 3. Reconsultar UUID tras adquirir el bloqueo.
        existente = buscar_movimiento_uuid(
            db, datos.uuid_local
        )

        if existente is not None:
            if (
                misma_solicitud(existente, datos)
                and existente.estado == "ACTIVO"
            ):
                resultado = respuesta_movimiento(
                    existente, creado=False
                )
                db.rollback()
                return resultado

            raise HTTPException(
                status_code=409,
                detail="UUID utilizado por otra operación"
            )

        # 4. Validar la categoría.
        categoria = buscar_categoria(
            db, datos.id_categoria
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
                detail="La categoría no corresponde al tipo"
            )

        if not (
            categoria.es_sistema
            or categoria.id_usuario == id_usuario
        ):
            raise HTTPException(
                status_code=403,
                detail="Categoría no autorizada"
            )

        # 5. Verificar fondos para gastos.
        if datos.tipo == "GASTO":
            saldo = calcular_saldo_cuenta(db, cuenta)

            if saldo < datos.monto:
                raise HTTPException(
                    status_code=409,
                    detail="Saldo insuficiente"
                )

        # 6. Crear movimiento normal.
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
            estado="ACTIVO"
        )

        agregar_movimiento(db, nuevo)

        resultado = respuesta_movimiento(
            nuevo, creado=True
        )

        # 7. Confirmar toda la operación.
        db.commit()
        return resultado

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflicto de integridad al registrar el movimiento"
        )

    except Exception:
        db.rollback()
        raise
