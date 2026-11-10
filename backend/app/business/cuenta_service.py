from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import CuentaFinanciera
from app.schemas.cuenta_schema import CuentaCrear
from app.schemas.cuenta_schema import CuentaActualizar

from app.persistence.cuenta_repository import (
    obtener_cuentas_con_saldo,
    buscar_cuenta_por_nombre,
    insertar_cuenta,
    bloquear_cuenta_usuario,
)

from app.persistence.movimiento_escritura_repository import (
    calcular_saldo_cuenta,
)

def consultar_resumen_cuentas(
    db: Session,
    id_usuario: int
):
    if id_usuario <= 0:
        raise ValueError("El identificador debe ser positivo")

    registros = obtener_cuentas_con_saldo(
        db=db,
        id_usuario=id_usuario
    )

    cuentas = [dict(registro) for registro in registros]

    # El saldo general incluye todas las cuentas
    # del usuario, incluso si estan inactivas.
    saldo_general = sum(
        (cuenta["saldo_actual"] for cuenta in cuentas),
        Decimal("0.00")
    )

    return {
        "id_usuario": id_usuario,
        "total_cuentas": len(cuentas),
        "saldo_general": saldo_general,
        "cuentas": cuentas
    }


def crear_cuenta_financiera(
    db: Session,
    id_usuario: int,
    datos: CuentaCrear
):
    if id_usuario <= 0:
        raise HTTPException(
            status_code=401,
            detail="Usuario no válido"
        )

    existente = buscar_cuenta_por_nombre(
        db=db,
        id_usuario=id_usuario,
        nombre_cuenta=datos.nombre_cuenta
    )

    if existente is not None:
        raise HTTPException(
            status_code=409,
            detail=(
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
        estado="ACTIVA"
    )

    try:
        insertar_cuenta(
            db=db,
            cuenta=nueva_cuenta
        )

        db.commit()
        db.refresh(nueva_cuenta)

        return nueva_cuenta

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
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
    cambios = datos.model_dump(exclude_unset=True)

    if not cambios:
        raise HTTPException(
            status_code=422,
            detail="Debes indicar al menos un campo"
        )

    if (
        "nombre_cuenta" in cambios
        and cambios["nombre_cuenta"] is None
    ):
        raise HTTPException(
            status_code=422,
            detail="El nombre no puede ser nulo"
        )

    try:
        cuenta = bloquear_cuenta_usuario(
            db=db,
            id_cuenta=id_cuenta,
            id_usuario=id_usuario
        )

        if cuenta is None:
            raise HTTPException(
                status_code=404,
                detail="Cuenta no encontrada"
            )

        if cuenta.estado != "ACTIVA":
            raise HTTPException(
                status_code=409,
                detail="No puedes editar una cuenta inactiva"
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
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Ya tienes otra cuenta "
                        "con ese nombre"
                    )
                )

            cuenta.nombre_cuenta = nombre

        if "institucion" in cambios:
            cuenta.institucion = cambios["institucion"]

        db.commit()
        db.refresh(cuenta)

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
            raise HTTPException(
                status_code=404,
                detail="Cuenta no encontrada"
            )

        if cuenta.estado not in ("ACTIVA", "INACTIVA"):
            raise HTTPException(
                status_code=409,
                detail="Estado de cuenta no válido"
            )

        if cuenta.estado == "ACTIVA":

            saldo_actual = calcular_saldo_cuenta(
                db,
                cuenta
            )

            if saldo_actual != Decimal("0.00"):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "No puedes desactivar una cuenta "
                        "con saldo diferente de cero. "
                        "Saldo actual: " +
                        str(saldo_actual)
                    )
                )

            cuenta.estado = "INACTIVA"

        db.commit()
        db.refresh(cuenta)

        return cuenta

    except Exception:
        db.rollback()
        raise
