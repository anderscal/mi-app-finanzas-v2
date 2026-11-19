
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ObligacionFinanciera

from app.schemas.obligacion_schema import (
    ObligacionCrear,
    ObligacionActualizar,
)

from app.persistence.obligacion_admin_repository import (
    bloquear_usuario,
    buscar_obligacion_duplicada,
    obtener_obligacion_usuario,
    bloquear_obligacion_usuario,
    contar_abonos_activos,
    insertar_obligacion,
)


def consultar_detalle_obligacion(
    db: Session,
    id_usuario: int,
    id_obligacion: int
):
    obligacion = obtener_obligacion_usuario(
        db,
        id_usuario,
        id_obligacion
    )

    if obligacion is None:
        raise HTTPException(
            status_code=404,
            detail="Obligación no encontrada"
        )

    return obligacion


def _bloquear_propietario(
    db: Session,
    id_usuario: int
):
    usuario = bloquear_usuario(
        db,
        id_usuario
    )

    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail="Usuario no válido"
        )


def _bloquear_obligacion_propia(
    db: Session,
    id_usuario: int,
    id_obligacion: int
):
    obligacion = bloquear_obligacion_usuario(
        db,
        id_usuario,
        id_obligacion
    )

    if obligacion is None:
        raise HTTPException(
            status_code=404,
            detail="Obligación no encontrada"
        )

    return obligacion


def crear_obligacion_financiera(
    db: Session,
    id_usuario: int,
    datos: ObligacionCrear
):
    try:
        _bloquear_propietario(
            db,
            id_usuario
        )

        existente = buscar_obligacion_duplicada(
            db,
            id_usuario,
            datos.nombre_obligacion,
            datos.tipo_obligacion
        )

        if existente is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ya existe una obligación "
                    "con ese nombre y tipo"
                )
            )

        obligacion = ObligacionFinanciera(
            id_usuario=id_usuario,
            nombre_obligacion=datos.nombre_obligacion,
            tipo_obligacion=datos.tipo_obligacion,
            monto_original=datos.monto_original,
            fecha_inicio=datos.fecha_inicio,
            fecha_vencimiento=datos.fecha_vencimiento,
            descripcion=datos.descripcion,
            estado="ACTIVA"
        )

        insertar_obligacion(
            db,
            obligacion
        )

        db.commit()
        db.refresh(obligacion)

        return obligacion

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflicto al crear la obligación"
        )

    except Exception:
        db.rollback()
        raise


def actualizar_obligacion_financiera(
    db: Session,
    id_usuario: int,
    id_obligacion: int,
    datos: ObligacionActualizar
):
    cambios = datos.model_dump(
        exclude_unset=True
    )

    if not cambios:
        raise HTTPException(
            status_code=422,
            detail="Indica al menos un campo para editar"
        )

    try:
        _bloquear_propietario(
            db,
            id_usuario
        )

        obligacion = _bloquear_obligacion_propia(
            db,
            id_usuario,
            id_obligacion
        )

        if obligacion.estado != "ACTIVA":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Solo pueden editarse "
                    "obligaciones activas"
                )
            )

        if "nombre_obligacion" in cambios:
            nombre = cambios["nombre_obligacion"]

            duplicada = buscar_obligacion_duplicada(
                db,
                id_usuario,
                nombre,
                obligacion.tipo_obligacion,
                id_excluir=id_obligacion
            )

            if duplicada is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Ya existe otra obligación "
                        "con ese nombre y tipo"
                    )
                )

            obligacion.nombre_obligacion = nombre

        if "fecha_vencimiento" in cambios:
            vencimiento = cambios["fecha_vencimiento"]

            if (
                vencimiento is not None
                and vencimiento < obligacion.fecha_inicio
            ):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "El vencimiento no puede "
                        "ser anterior al inicio"
                    )
                )

            obligacion.fecha_vencimiento = vencimiento

        if "descripcion" in cambios:
            obligacion.descripcion = cambios["descripcion"]

        db.commit()
        db.refresh(obligacion)

        return obligacion

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflicto al editar la obligación"
        )

    except Exception:
        db.rollback()
        raise


def desactivar_obligacion_financiera(
    db: Session,
    id_usuario: int,
    id_obligacion: int
):
    try:
        _bloquear_propietario(
            db,
            id_usuario
        )

        obligacion = _bloquear_obligacion_propia(
            db,
            id_usuario,
            id_obligacion
        )

        if obligacion.estado == "INACTIVA":
            db.commit()
            db.refresh(obligacion)
            return obligacion

        if obligacion.estado != "ACTIVA":
            raise HTTPException(
                status_code=409,
                detail=(
                    "No se puede desactivar "
                    "una obligación saldada"
                )
            )

        if contar_abonos_activos(
            db,
            id_obligacion
        ) > 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    "No puedes desactivar una obligación "
                    "que tiene abonos activos. "
                    "Su historial debe conservarse."
                )
            )

        obligacion.estado = "INACTIVA"

        db.commit()
        db.refresh(obligacion)

        return obligacion

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflicto al desactivar la obligación"
        )

    except Exception:
        db.rollback()
        raise
