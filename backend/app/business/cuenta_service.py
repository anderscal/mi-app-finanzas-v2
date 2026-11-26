
from decimal import Decimal

from app.persistence.unidad_trabajo_repository import refrescar_entidad
from app.business.errores import CodigoError, ErrorNegocio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CuentaFinanciera

from app.schemas.cuenta_schema import (
    CuentaCrear,
    CuentaActualizar,
)

from app.persistence.cuenta_repository import (
    obtener_cuentas_con_saldo,
    buscar_cuenta_por_nombre,
    insertar_cuenta,
    bloquear_cuenta_usuario,
)

from app.business.saldo_libre_service import (
    consultar_disponibilidad_cuenta,
)


CERO = Decimal("0.00")


def consultar_resumen_cuentas(
    db: Session,
    id_usuario: int
):
    if id_usuario <= 0:
        raise ValueError(
            "El identificador debe ser positivo"
        )

    registros = obtener_cuentas_con_saldo(
        db=db,
        id_usuario=id_usuario
    )

    cuentas = [
        dict(registro)
        for registro in registros
    ]

    saldo_general = sum(
        (
            cuenta["saldo_actual"]
            for cuenta in cuentas
        ),
        CERO
    )

    return {
        "id_usuario": id_usuario,
        "total_cuentas": len(cuentas),
        "saldo_general": saldo_general,
        "cuentas": cuentas,
    }


def crear_cuenta_financiera(
    db: Session,
    id_usuario: int,
    datos: CuentaCrear
):
    if id_usuario <= 0:
        raise ErrorNegocio(
            codigo=CodigoError.NO_AUTENTICADO,
            detalle="Usuario no válido"
        )

    existente = buscar_cuenta_por_nombre(
        db=db,
        id_usuario=id_usuario,
        nombre_cuenta=datos.nombre_cuenta
    )

    if existente is not None:
        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "Ya tienes una cuenta financiera "
                "con ese nombre"
            )
        )

    nueva_cuenta = CuentaFinanciera(
        id_usuario=id_usuario,
        nombre_cuenta=datos.nombre_cuenta,
        tipo_cuenta=datos.tipo_cuenta,
        institucion=datos.institucion,
        saldo_inicial=datos.saldo_inicial,
        estado="ACTIVA",
    )

    try:
        insertar_cuenta(
            db=db,
            cuenta=nueva_cuenta
        )

        db.commit()
        refrescar_entidad(db, nueva_cuenta)

        return nueva_cuenta

    except IntegrityError:
        db.rollback()

        raise ErrorNegocio(
            codigo=CodigoError.CONFLICTO,
            detalle=(
                "No fue posible crear la cuenta "
                "por un conflicto de integridad"
            )
        )

    except Exception:
        db.rollback()
        raise


def actualizar_cuenta_financiera(
    db: Session,
    id_usuario: int,
    id_cuenta: int,
    datos: CuentaActualizar
):
    cambios = datos.model_dump(
        exclude_unset=True
    )

    if not cambios:
        raise ErrorNegocio(
            codigo=CodigoError.VALIDACION,
            detalle="Debes indicar al menos un campo"
        )

    if (
        "nombre_cuenta" in cambios
        and cambios["nombre_cuenta"] is None
    ):
        raise ErrorNegocio(
            codigo=CodigoError.VALIDACION,
            detalle="El nombre no puede ser nulo"
        )

    try:
        cuenta = bloquear_cuenta_usuario(
            db=db,
            id_cuenta=id_cuenta,
            id_usuario=id_usuario
        )

        if cuenta is None:
            raise ErrorNegocio(
                codigo=CodigoError.NO_ENCONTRADO,
                detalle="Cuenta no encontrada"
            )

        if cuenta.estado != "ACTIVA":
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle="No puedes editar una cuenta inactiva"
            )

        if "nombre_cuenta" in cambios:
            nombre = cambios["nombre_cuenta"]

            existente = buscar_cuenta_por_nombre(
                db=db,
                id_usuario=id_usuario,
                nombre_cuenta=nombre
            )

            if (
                existente is not None
                and existente.id_cuenta != cuenta.id_cuenta
            ):
                raise ErrorNegocio(
                    codigo=CodigoError.CONFLICTO,
                    detalle=(
                        "Ya tienes otra cuenta "
                        "con ese nombre"
                    )
                )

            cuenta.nombre_cuenta = nombre

        if "institucion" in cambios:
            cuenta.institucion = cambios["institucion"]

        db.commit()
        refrescar_entidad(db, cuenta)

        return cuenta

    except Exception:
        db.rollback()
        raise


def desactivar_cuenta_financiera(
    db: Session,
    id_usuario: int,
    id_cuenta: int
):
    try:
        cuenta = bloquear_cuenta_usuario(
            db=db,
            id_cuenta=id_cuenta,
            id_usuario=id_usuario
        )

        if cuenta is None:
            raise ErrorNegocio(
                codigo=CodigoError.NO_ENCONTRADO,
                detalle="Cuenta no encontrada"
            )

        if cuenta.estado not in ("ACTIVA", "INACTIVA"):
            raise ErrorNegocio(
                codigo=CodigoError.CONFLICTO,
                detalle="Estado de cuenta no válido"
            )

        if cuenta.estado == "ACTIVA":
            disponibilidad = (
                consultar_disponibilidad_cuenta(
                    db,
                    cuenta
                )
            )

            reservado = disponibilidad[
                "monto_reservado"
            ]

            if reservado > CERO:
                raise ErrorNegocio(
                    codigo=CodigoError.CONFLICTO,
                    detalle=(
                        "No puedes desactivar una cuenta "
                        "que tiene dinero reservado "
                        "para metas de ahorro. "
                        "Libera primero "
                        f"{reservado:.2f}"
                    )
                )

            if reservado < CERO:
                raise ErrorNegocio(
                    codigo=CodigoError.CONFLICTO,
                    detalle="La cuenta tiene reservas inconsistentes"
                )

            saldo_real = disponibilidad[
                "saldo_real"
            ]

            if saldo_real != CERO:
                raise ErrorNegocio(
                    codigo=CodigoError.CONFLICTO,
                    detalle=(
                        "No puedes desactivar una cuenta "
                        "con saldo diferente de cero. "
                        f"Saldo actual: {saldo_real:.2f}"
                    )
                )

            cuenta.estado = "INACTIVA"

        db.commit()
        refrescar_entidad(db, cuenta)

        return cuenta

    except Exception:
        db.rollback()
        raise
