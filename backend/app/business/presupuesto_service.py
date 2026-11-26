
from app.persistence.unidad_trabajo_repository import refrescar_entidad
from app.business.errores import CodigoError, ErrorNegocio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Presupuesto

from app.schemas.presupuesto_schema import (
    PresupuestoCrear,
    PresupuestoActualizar,
)

from app.persistence.presupuesto_repository import (
    bloquear_usuario,
    obtener_categoria_presupuesto,
    obtener_presupuestos_usuario,
    buscar_presupuesto_periodo,
    bloquear_presupuesto_usuario,
    insertar_presupuesto,
)


def consultar_presupuestos(
    db: Session,
    id_usuario: int
):
    return obtener_presupuestos_usuario(
        db=db,
        id_usuario=id_usuario
    )


def _validar_usuario(
    db: Session,
    id_usuario: int
):
    usuario = bloquear_usuario(
        db=db,
        id_usuario=id_usuario
    )

    if usuario is None:
        raise ErrorNegocio(
            codigo=CodigoError.NO_AUTENTICADO,
            detalle="Usuario no válido"
        )


def _validar_categoria(
    db: Session,
    id_usuario: int,
    id_categoria: int
):
    categoria = obtener_categoria_presupuesto(
        db=db,
        id_categoria=id_categoria
    )

    if categoria is None:
        raise ErrorNegocio(
            codigo=CodigoError.NO_ENCONTRADO,
            detalle="Categoría no encontrada"
        )

    es_global = (
        categoria.es_sistema is True
        and categoria.id_usuario is None
    )

    es_personal = (
        categoria.es_sistema is False
        and categoria.id_usuario == id_usuario
    )

    if not (es_global or es_personal):
        raise ErrorNegocio(
            codigo=CodigoError.NO_ENCONTRADO,
            detalle="Categoría no encontrada"
        )

    if categoria.estado != "ACTIVA":
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="La categoría está inactiva"
        )

    if categoria.tipo_categoria != "GASTO":
        raise ErrorNegocio(
            codigo=CodigoError.VALIDACION,
            detalle=(
                "Los presupuestos solo pueden "
                "asociarse a categorías de gasto"
            )
        )

    return categoria


def crear_presupuesto_financiero(
    db: Session,
    id_usuario: int,
    datos: PresupuestoCrear
):
    try:
        _validar_usuario(
            db=db,
            id_usuario=id_usuario
        )

        _validar_categoria(
            db=db,
            id_usuario=id_usuario,
            id_categoria=datos.id_categoria
        )

        duplicado = buscar_presupuesto_periodo(
            db=db,
            id_usuario=id_usuario,
            id_categoria=datos.id_categoria,
            anio=datos.anio,
            mes=datos.mes
        )

        if duplicado is not None:
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle=(
                    "Ya existe un presupuesto para "
                    "esta categoría y período"
                )
            )

        presupuesto = Presupuesto(
            id_usuario=id_usuario,
            id_categoria=datos.id_categoria,
            anio=datos.anio,
            mes=datos.mes,
            monto_limite=datos.monto_limite
        )

        insertar_presupuesto(
            db=db,
            presupuesto=presupuesto
        )

        db.commit()
        refrescar_entidad(db, presupuesto)

        return presupuesto

    except IntegrityError:
        db.rollback()

        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "Conflicto de integridad al crear "
                "el presupuesto"
            )
        )

    except Exception:
        db.rollback()
        raise


def actualizar_presupuesto_financiero(
    db: Session,
    id_usuario: int,
    id_presupuesto: int,
    datos: PresupuestoActualizar
):
    try:
        _validar_usuario(
            db=db,
            id_usuario=id_usuario
        )

        presupuesto = bloquear_presupuesto_usuario(
            db=db,
            id_usuario=id_usuario,
            id_presupuesto=id_presupuesto
        )

        if presupuesto is None:
            raise ErrorNegocio(
                codigo=CodigoError.NO_ENCONTRADO,
                detalle="Presupuesto no encontrado"
            )

        presupuesto.monto_limite = datos.monto_limite

        db.commit()
        refrescar_entidad(db, presupuesto)

        return presupuesto

    except IntegrityError:
        db.rollback()

        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "Conflicto de integridad al actualizar "
                "el presupuesto"
            )
        )

    except Exception:
        db.rollback()
        raise
