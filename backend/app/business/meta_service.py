
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import MetaFinanciera

from app.schemas.meta_schema import (
    MetaCrear,
    MetaActualizar,
    MetaAporteCrear,
)

from app.persistence.meta_repository import (
    bloquear_usuario_meta,
    listar_metas_usuario,
    obtener_meta_usuario,
    bloquear_meta_usuario,
    buscar_meta_nombre,
    insertar_meta,
)


CERO = Decimal("0.00")
CIEN = Decimal("100.00")


def _bloquear_propietario(
    db: Session,
    id_usuario: int
):
    usuario = bloquear_usuario_meta(
        db,
        id_usuario
    )

    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail="Usuario no válido"
        )


def _meta_propia_bloqueada(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    meta = bloquear_meta_usuario(
        db,
        id_usuario,
        id_meta
    )

    if meta is None:
        raise HTTPException(
            status_code=404,
            detail="Meta no encontrada"
        )

    return meta


def _porcentaje(meta: MetaFinanciera) -> Decimal:
    return (
        meta.monto_acumulado
        / meta.monto_objetivo
        * CIEN
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def _resultado_aporte(
    meta: MetaFinanciera,
    creado: bool
):
    return {
        "id_meta": meta.id_meta,
        "monto_objetivo": meta.monto_objetivo,
        "monto_acumulado": meta.monto_acumulado,
        "porcentaje_progreso": _porcentaje(meta),
        "estado": meta.estado,
        "creado": creado,
        "mensaje": (
            "Aporte registrado correctamente"
            if creado
            else "Aporte ya reflejado en la meta"
        )
    }


def consultar_metas(
    db: Session,
    id_usuario: int
):
    return listar_metas_usuario(
        db,
        id_usuario
    )


def consultar_meta(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    meta = obtener_meta_usuario(
        db,
        id_usuario,
        id_meta
    )

    if meta is None:
        raise HTTPException(
            status_code=404,
            detail="Meta no encontrada"
        )

    return meta


def crear_meta(
    db: Session,
    id_usuario: int,
    datos: MetaCrear
):
    try:
        _bloquear_propietario(
            db,
            id_usuario
        )

        duplicada = buscar_meta_nombre(
            db,
            id_usuario,
            datos.nombre_meta
        )

        if duplicada is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ya existe una meta con ese nombre"
                )
            )

        meta = MetaFinanciera(
            id_usuario=id_usuario,
            nombre_meta=datos.nombre_meta,
            monto_objetivo=datos.monto_objetivo,
            monto_acumulado=CERO,
            fecha_objetivo=datos.fecha_objetivo,
            descripcion=datos.descripcion,
            estado="ACTIVA"
        )

        insertar_meta(
            db,
            meta
        )

        db.commit()
        db.refresh(meta)

        return meta

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Conflicto al crear la meta"
        )

    except Exception:
        db.rollback()
        raise


def actualizar_meta(
    db: Session,
    id_usuario: int,
    id_meta: int,
    datos: MetaActualizar
):
    cambios = datos.model_dump(
        exclude_unset=True
    )

    if not cambios:
        raise HTTPException(
            status_code=422,
            detail="Indica al menos un cambio"
        )

    try:
        _bloquear_propietario(
            db,
            id_usuario
        )

        meta = _meta_propia_bloqueada(
            db,
            id_usuario,
            id_meta
        )

        if meta.estado == "INACTIVA":
            raise HTTPException(
                status_code=409,
                detail="La meta está inactiva"
            )

        if "nombre_meta" in cambios:
            nombre = cambios["nombre_meta"]

            duplicada = buscar_meta_nombre(
                db,
                id_usuario,
                nombre,
                id_excluir=id_meta
            )

            if duplicada is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Ya existe otra meta "
                        "con ese nombre"
                    )
                )

            meta.nombre_meta = nombre

        if "monto_objetivo" in cambios:
            objetivo = cambios["monto_objetivo"]

            if objetivo < meta.monto_acumulado:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "El objetivo no puede ser menor "
                        "que el ahorro acumulado"
                    )
                )

            meta.monto_objetivo = objetivo

        if "fecha_objetivo" in cambios:
            fecha = cambios["fecha_objetivo"]

            if fecha is None:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "La fecha objetivo es obligatoria"
                    )
                )

            if fecha < date.today():
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "La nueva fecha objetivo "
                        "no puede ser pasada"
                    )
                )

            meta.fecha_objetivo = fecha

        if "descripcion" in cambios:
            meta.descripcion = cambios["descripcion"]

        meta.estado = (
            "CUMPLIDA"
            if meta.monto_acumulado == meta.monto_objetivo
            else "ACTIVA"
        )

        db.commit()
        db.refresh(meta)

        return meta

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Conflicto al editar la meta"
        )

    except Exception:
        db.rollback()
        raise


def registrar_aporte_meta(
    db: Session,
    id_usuario: int,
    id_meta: int,
    datos: MetaAporteCrear
):
    try:
        _bloquear_propietario(
            db,
            id_usuario
        )

        meta = _meta_propia_bloqueada(
            db,
            id_usuario,
            id_meta
        )

        esperado = datos.acumulado_esperado
        resultado_esperado = esperado + datos.monto

        # Reintento de la misma actualización:
        # el acumulado ya tiene el valor previsto.
        if meta.monto_acumulado == resultado_esperado:
            respuesta = _resultado_aporte(
                meta,
                creado=False
            )

            db.commit()
            return respuesta

        if meta.estado != "ACTIVA":
            raise HTTPException(
                status_code=409,
                detail=(
                    "La meta no admite nuevos aportes"
                )
            )

        if meta.monto_acumulado != esperado:
            raise HTTPException(
                status_code=409,
                detail=(
                    "El acumulado cambió. "
                    "Actualiza la meta antes de aportar"
                )
            )

        if resultado_esperado > meta.monto_objetivo:
            raise HTTPException(
                status_code=409,
                detail=(
                    "El aporte supera el objetivo "
                    "pendiente de la meta"
                )
            )

        meta.monto_acumulado = resultado_esperado

        if meta.monto_acumulado == meta.monto_objetivo:
            meta.estado = "CUMPLIDA"

        db.flush()

        respuesta = _resultado_aporte(
            meta,
            creado=True
        )

        db.commit()

        return respuesta

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Conflicto al registrar el aporte"
        )

    except Exception:
        db.rollback()
        raise


def desactivar_meta(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    try:
        _bloquear_propietario(
            db,
            id_usuario
        )

        meta = _meta_propia_bloqueada(
            db,
            id_usuario,
            id_meta
        )

        if meta.estado == "INACTIVA":
            db.commit()
            return meta

        if meta.monto_acumulado > CERO:
            raise HTTPException(
                status_code=409,
                detail=(
                    "No puedes desactivar una meta "
                    "que tiene ahorro acumulado"
                )
            )

        meta.estado = "INACTIVA"

        db.commit()
        db.refresh(meta)

        return meta

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Conflicto al desactivar la meta"
        )

    except Exception:
        db.rollback()
        raise
