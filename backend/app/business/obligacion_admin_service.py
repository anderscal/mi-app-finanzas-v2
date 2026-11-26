
from decimal import Decimal, ROUND_HALF_UP

from app.persistence.unidad_trabajo_repository import refrescar_entidad
from app.business.errores import CodigoError, ErrorNegocio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Movimiento,
    ObligacionFinanciera,
)

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

from app.persistence.movimiento_escritura_repository import (
    bloquear_cuenta,
    buscar_movimiento_uuid,
    agregar_movimiento,
)

from app.business.saldo_libre_service import (
    exigir_saldo_libre,
)


TASA_GMF = Decimal("0.004")

DESCRIPCION_INICIAL = (
    "Capital inicial de obligación"
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
        raise ErrorNegocio(
            codigo=CodigoError.NO_ENCONTRADO,
            detalle="Obligación no encontrada"
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
        raise ErrorNegocio(
            codigo=CodigoError.NO_AUTENTICADO,
            detalle="Usuario no válido"
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
        raise ErrorNegocio(
            codigo=CodigoError.NO_ENCONTRADO,
            detalle="Obligación no encontrada"
        )

    return obligacion


def _tipo_movimiento_inicial(
    tipo_obligacion: str
) -> str:
    if tipo_obligacion == "POR_PAGAR":
        return "INGRESO"

    if tipo_obligacion == "POR_COBRAR":
        return "GASTO"

    raise ErrorNegocio(
        codigo=CodigoError.VALIDACION,
        detalle="Tipo de obligación no válido"
    )


def _gmf_inicial(
    datos: ObligacionCrear
) -> Decimal:
    if not datos.aplica_gmf_inicial:
        return Decimal("0.00")

    return (
        datos.monto_original * TASA_GMF
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def _buscar_creacion_existente(
    db: Session,
    id_usuario: int,
    datos: ObligacionCrear
):
    if not datos.registrar_movimiento_inicial:
        return None

    movimiento = buscar_movimiento_uuid(
        db,
        datos.uuid_local_inicial
    )

    if movimiento is None:
        return None

    if movimiento.id_obligacion is None:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="UUID utilizado por otra operación"
        )

    obligacion = obtener_obligacion_usuario(
        db,
        id_usuario,
        movimiento.id_obligacion
    )

    if (
        obligacion is None
        or obligacion.id_usuario != id_usuario
    ):
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="UUID utilizado por otra operación"
        )

    coincide = (
        movimiento.estado == "ACTIVO"
        and movimiento.origen == "OBLIGACION"
        and movimiento.tipo
            == _tipo_movimiento_inicial(
                datos.tipo_obligacion
            )
        and movimiento.id_cuenta
            == datos.id_cuenta_inicial
        and movimiento.id_categoria is None
        and movimiento.id_transferencia is None
        and movimiento.monto == datos.monto_original
        and movimiento.fecha_movimiento
            == datos.fecha_inicio
        and movimiento.descripcion
            == DESCRIPCION_INICIAL
        and movimiento.aplica_gmf
            == datos.aplica_gmf_inicial
        and movimiento.monto_gmf
            == _gmf_inicial(datos)
        and obligacion.nombre_obligacion
            == datos.nombre_obligacion
        and obligacion.tipo_obligacion
            == datos.tipo_obligacion
        and obligacion.monto_original
            == datos.monto_original
        and obligacion.fecha_inicio
            == datos.fecha_inicio
        and obligacion.fecha_vencimiento
            == datos.fecha_vencimiento
        and obligacion.descripcion
            == datos.descripcion
    )

    if not coincide:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="UUID ya utilizado con datos diferentes"
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

        existente = _buscar_creacion_existente(
            db,
            id_usuario,
            datos
        )

        if existente is not None:
            db.rollback()
            return existente

        duplicada = buscar_obligacion_duplicada(
            db,
            id_usuario,
            datos.nombre_obligacion,
            datos.tipo_obligacion
        )

        if duplicada is not None:
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle=(
                    "Ya existe una obligación "
                    "con ese nombre y tipo"
                )
            )

        cuenta = None
        monto_gmf = Decimal("0.00")

        if datos.registrar_movimiento_inicial:
            cuenta = bloquear_cuenta(
                db,
                datos.id_cuenta_inicial,
                id_usuario
            )

            if cuenta is None:
                raise ErrorNegocio(
                    codigo=CodigoError.NO_ENCONTRADO,
                    detalle="Cuenta no encontrada"
                )

            if cuenta.estado != "ACTIVA":
                raise ErrorNegocio(
                    codigo=CodigoError.CONFLICTO,
                    detalle="La cuenta está inactiva"
                )

            monto_gmf = _gmf_inicial(
                datos
            )

            # POR_COBRAR implica prestar dinero:
            # salida de capital desde una cuenta.
            if datos.tipo_obligacion == "POR_COBRAR":
                exigir_saldo_libre(
                    db,
                    cuenta,
                    datos.monto_original + monto_gmf
                )

            # Idempotencia después de bloquear.
            existente = _buscar_creacion_existente(
                db,
                id_usuario,
                datos
            )

            if existente is not None:
                db.rollback()
                return existente

        obligacion = ObligacionFinanciera(
            id_usuario=id_usuario,
            nombre_obligacion=datos.nombre_obligacion,
            tipo_obligacion=datos.tipo_obligacion,
            monto_original=datos.monto_original,
            fecha_inicio=datos.fecha_inicio,
            fecha_vencimiento=datos.fecha_vencimiento,
            descripcion=datos.descripcion,
            estado="ACTIVA",
        )

        insertar_obligacion(
            db,
            obligacion
        )

        if datos.registrar_movimiento_inicial:
            movimiento = Movimiento(
                uuid_local=datos.uuid_local_inicial,
                id_cuenta=cuenta.id_cuenta,
                id_categoria=None,
                id_transferencia=None,
                id_obligacion=obligacion.id_obligacion,
                tipo=_tipo_movimiento_inicial(
                    datos.tipo_obligacion
                ),
                origen="OBLIGACION",
                monto=datos.monto_original,
                fecha_movimiento=datos.fecha_inicio,
                descripcion=DESCRIPCION_INICIAL,
                aplica_gmf=datos.aplica_gmf_inicial,
                monto_gmf=monto_gmf,
                estado="ACTIVO",
            )

            agregar_movimiento(
                db,
                movimiento
            )

        db.commit()
        refrescar_entidad(db, obligacion)

        return obligacion

    except IntegrityError:
        db.rollback()
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "Conflicto de integridad al crear "
                "la obligación"
            )
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
        raise ErrorNegocio(
            codigo=CodigoError.VALIDACION,
            detalle="Indica al menos un campo para editar"
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
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle=(
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
                raise ErrorNegocio(
                    codigo=CodigoError.CONFLICTO,
                    detalle=(
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
                raise ErrorNegocio(
                    codigo=CodigoError.VALIDACION,
                    detalle=(
                        "El vencimiento no puede "
                        "ser anterior al inicio"
                    )
                )

            obligacion.fecha_vencimiento = vencimiento

        if "descripcion" in cambios:
            obligacion.descripcion = cambios["descripcion"]

        db.commit()
        refrescar_entidad(db, obligacion)

        return obligacion

    except IntegrityError:
        db.rollback()
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle="Conflicto al editar la obligación"
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
            refrescar_entidad(db, obligacion)
            return obligacion

        if obligacion.estado != "ACTIVA":
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle=(
                    "No se puede desactivar "
                    "una obligación saldada"
                )
            )

        if contar_abonos_activos(
            db,
            id_obligacion
        ) > 0:
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle=(
                    "No puedes desactivar una obligación "
                    "con movimientos financieros activos"
                )
            )

        obligacion.estado = "INACTIVA"

        db.commit()
        refrescar_entidad(db, obligacion)

        return obligacion

    except IntegrityError:
        db.rollback()
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "Conflicto al desactivar la obligación"
            )
        )

    except Exception:
        db.rollback()
        raise
