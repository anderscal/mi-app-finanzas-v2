
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AporteMeta

from app.schemas.meta_reserva_schema import (
    OperacionReservaCrear,
)

from app.persistence.meta_reserva_repository import (
    bloquear_usuario_reservas,
    bloquear_cuenta_reserva,
    bloquear_meta_reserva,
    obtener_meta_reserva,
    obtener_cuentas_reserva,
    buscar_aporte_uuid,
    existe_uuid_movimiento_bancario,
    reservado_por_cuenta,
    reservado_por_meta,
    listar_eventos_meta,
    insertar_evento_reserva,
)

from app.persistence.movimiento_escritura_repository import (
    calcular_saldo_cuenta,
)


CERO = Decimal("0.00")


def _validar_usuario(
    db: Session,
    id_usuario: int
):
    usuario = bloquear_usuario_reservas(
        db,
        id_usuario
    )

    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail="Usuario no válido"
        )

    return usuario


def _obtener_cuenta_bloqueada(
    db: Session,
    id_usuario: int,
    id_cuenta: int
):
    cuenta = bloquear_cuenta_reserva(
        db,
        id_usuario,
        id_cuenta
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

    return cuenta


def _obtener_meta_bloqueada(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    meta = bloquear_meta_reserva(
        db,
        id_usuario,
        id_meta
    )

    if meta is None:
        raise HTTPException(
            status_code=404,
            detail="Meta no encontrada"
        )

    if meta.estado not in ("ACTIVA", "CUMPLIDA"):
        raise HTTPException(
            status_code=409,
            detail="La meta está inactiva"
        )

    return meta


def _validar_consistencia(
    db: Session,
    id_usuario: int,
    meta
):
    vinculado = reservado_por_meta(
        db,
        id_usuario,
        meta.id_meta
    )

    if (
        vinculado < CERO
        or vinculado > meta.monto_acumulado
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Los aportes de la meta no coinciden "
                "con sus reservas. Requiere conciliación"
            )
        )

    return vinculado


def _respuesta_operacion(
    db: Session,
    id_usuario: int,
    evento: AporteMeta,
    creado: bool
):
    cuenta = bloquear_cuenta_reserva(
        db,
        id_usuario,
        evento.id_cuenta
    )

    meta = bloquear_meta_reserva(
        db,
        id_usuario,
        evento.id_meta
    )

    if cuenta is None or meta is None:
        raise HTTPException(
            status_code=409,
            detail="Datos financieros inconsistentes"
        )

    saldo_real = calcular_saldo_cuenta(
        db,
        cuenta
    )

    reservado = reservado_por_cuenta(
        db,
        id_usuario,
        cuenta.id_cuenta
    )

    return {
        "id_aporte": evento.id_aporte,
        "uuid_operacion": evento.uuid_operacion,
        "id_meta": evento.id_meta,
        "id_cuenta": evento.id_cuenta,
        "tipo": evento.tipo,
        "monto": evento.monto,
        "monto_acumulado": meta.monto_acumulado,
        "reservado_en_cuenta": reservado,
        "saldo_real": saldo_real,
        "saldo_libre": saldo_real - reservado,
        "creado": creado
    }


def _revisar_reintento(
    db: Session,
    id_usuario: int,
    id_meta: int,
    tipo: str,
    datos: OperacionReservaCrear
):
    existente = buscar_aporte_uuid(
        db,
        datos.uuid_operacion
    )

    if existente is None:
        return None

    misma_operacion = (
        existente.id_usuario == id_usuario
        and existente.id_meta == id_meta
        and existente.id_cuenta == datos.id_cuenta
        and existente.tipo == tipo
        and existente.monto == datos.monto
        and existente.fecha_operacion
            == datos.fecha_operacion
        and existente.estado == "ACTIVO"
    )

    if not misma_operacion:
        raise HTTPException(
            status_code=409,
            detail=(
                "UUID ya utilizado con otros datos "
                "o por otra operación"
            )
        )

    return _respuesta_operacion(
        db,
        id_usuario,
        existente,
        creado=False
    )


def _registrar_operacion(
    db: Session,
    id_usuario: int,
    id_meta: int,
    datos: OperacionReservaCrear,
    tipo: str
):
    if tipo not in ("RESERVA", "LIBERACION"):
        raise HTTPException(
            status_code=422,
            detail="Tipo de operación no válido"
        )

    try:
        # Reconocer un reintento ya confirmado.
        anterior = _revisar_reintento(
            db,
            id_usuario,
            id_meta,
            tipo,
            datos
        )

        if anterior is not None:
            db.rollback()
            return anterior

        # Serializar reservas del mismo usuario.
        _validar_usuario(
            db,
            id_usuario
        )

        # Mantener un orden estable de bloqueos:
        # usuario -> cuenta -> meta.
        cuenta = _obtener_cuenta_bloqueada(
            db,
            id_usuario,
            datos.id_cuenta
        )

        meta = _obtener_meta_bloqueada(
            db,
            id_usuario,
            id_meta
        )

        # Revisar otra vez el UUID después
        # de obtener los bloqueos.
        anterior = _revisar_reintento(
            db,
            id_usuario,
            id_meta,
            tipo,
            datos
        )

        if anterior is not None:
            db.rollback()
            return anterior

        # Evitar reutilizar un UUID bancario
        # para crear una reserva nueva.
        if existe_uuid_movimiento_bancario(
            db,
            datos.uuid_operacion
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "El UUID pertenece a un "
                    "movimiento bancario"
                )
            )

        _validar_consistencia(
            db,
            id_usuario,
            meta
        )

        saldo_real = calcular_saldo_cuenta(
            db,
            cuenta
        )

        reservado_cuenta = reservado_por_cuenta(
            db,
            id_usuario,
            cuenta.id_cuenta
        )

        if reservado_cuenta < CERO:
            raise HTTPException(
                status_code=409,
                detail=(
                    "La cuenta tiene reservas "
                    "inconsistentes"
                )
            )

        if tipo == "RESERVA":
            if meta.estado != "ACTIVA":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "La meta ya está cumplida. "
                        "No admite más reservas"
                    )
                )

            saldo_libre = (
                saldo_real - reservado_cuenta
            )

            if saldo_libre < datos.monto:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Saldo libre insuficiente "
                        "para reservar el dinero"
                    )
                )

            nuevo_acumulado = (
                meta.monto_acumulado + datos.monto
            )

            if nuevo_acumulado > meta.monto_objetivo:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "La reserva supera lo "
                        "pendiente de la meta"
                    )
                )

        else:
            # Solo se puede liberar dinero que
            # realmente fue reservado desde
            # esta cuenta para esta meta.
            reservado_en_meta_cuenta = CERO

            for evento in listar_eventos_meta(
                db,
                id_usuario,
                id_meta
            ):
                if (
                    evento.id_cuenta
                    != cuenta.id_cuenta
                    or evento.estado != "ACTIVO"
                ):
                    continue

                if evento.tipo == "RESERVA":
                    reservado_en_meta_cuenta += evento.monto

                elif evento.tipo == "LIBERACION":
                    reservado_en_meta_cuenta -= evento.monto

            if reservado_en_meta_cuenta < datos.monto:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "No hay suficiente dinero "
                        "reservado en esta cuenta "
                        "para esta meta"
                    )
                )

            nuevo_acumulado = (
                meta.monto_acumulado - datos.monto
            )

            if nuevo_acumulado < CERO:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "La liberación supera el "
                        "ahorro acumulado"
                    )
                )

        # Guardar evento y progreso dentro
        # de la misma transacción.
        evento = AporteMeta(
            uuid_operacion=datos.uuid_operacion,
            id_usuario=id_usuario,
            id_meta=id_meta,
            id_cuenta=datos.id_cuenta,
            tipo=tipo,
            monto=datos.monto,
            fecha_operacion=datos.fecha_operacion,
            estado="ACTIVO"
        )

        insertar_evento_reserva(
            db,
            evento
        )

        meta.monto_acumulado = nuevo_acumulado

        meta.estado = (
            "CUMPLIDA"
            if nuevo_acumulado == meta.monto_objetivo
            else "ACTIVA"
        )

        db.flush()

        resultado = _respuesta_operacion(
            db,
            id_usuario,
            evento,
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
                "la reserva. Verifica los datos "
                "antes de reintentar"
            )
        )

    except Exception:
        db.rollback()
        raise


def reservar_dinero_meta(
    db: Session,
    id_usuario: int,
    id_meta: int,
    datos: OperacionReservaCrear
):
    return _registrar_operacion(
        db,
        id_usuario,
        id_meta,
        datos,
        "RESERVA"
    )


def liberar_dinero_meta(
    db: Session,
    id_usuario: int,
    id_meta: int,
    datos: OperacionReservaCrear
):
    return _registrar_operacion(
        db,
        id_usuario,
        id_meta,
        datos,
        "LIBERACION"
    )


def consultar_saldos_reservados(
    db: Session,
    id_usuario: int
):
    resultado = []

    for cuenta in obtener_cuentas_reserva(
        db,
        id_usuario
    ):
        saldo_real = calcular_saldo_cuenta(
            db,
            cuenta
        )

        reservado = reservado_por_cuenta(
            db,
            id_usuario,
            cuenta.id_cuenta
        )

        resultado.append({
            "id_cuenta": cuenta.id_cuenta,
            "nombre_cuenta": cuenta.nombre_cuenta,
            "estado": cuenta.estado,
            "saldo_real": saldo_real,
            "monto_reservado": reservado,
            "saldo_libre": saldo_real - reservado
        })

    return resultado


def consultar_detalle_reservas(
    db: Session,
    id_usuario: int,
    id_meta: int
):
    meta = obtener_meta_reserva(
        db,
        id_usuario,
        id_meta
    )

    if meta is None:
        raise HTTPException(
            status_code=404,
            detail="Meta no encontrada"
        )

    vinculado = reservado_por_meta(
        db,
        id_usuario,
        id_meta
    )

    return {
        "id_meta": meta.id_meta,
        "nombre_meta": meta.nombre_meta,
        "monto_objetivo": meta.monto_objetivo,
        "monto_acumulado": meta.monto_acumulado,
        "monto_vinculado": vinculado,
        "monto_sin_vincular": (
            meta.monto_acumulado - vinculado
        ),
        "registros": listar_eventos_meta(
            db,
            id_usuario,
            id_meta
        )
    }
