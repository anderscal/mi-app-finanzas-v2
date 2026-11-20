
from fastapi import (
    APIRouter,
    status,
)

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.meta_schema import (
    MetaCrear,
    MetaActualizar,
    MetaAporteCrear,
    MetaRespuesta,
    MetaAporteRespuesta,
)

from app.business.meta_service import (
    consultar_metas,
    consultar_meta,
    crear_meta,
    actualizar_meta,
    registrar_aporte_meta,
    desactivar_meta,
)

from app.schemas.meta_reserva_schema import (
    OperacionReservaCrear,
    OperacionReservaRespuesta,
    SaldoReservaCuentaRespuesta,
    DetalleReservasMetaRespuesta,
)

from app.business.meta_reserva_service import (
    reservar_dinero_meta,
    liberar_dinero_meta,
    consultar_saldos_reservados,
    consultar_detalle_reservas,
)


router = APIRouter(
    prefix="/metas",
    tags=["Metas de ahorro"]
)


# --------------------------------------
# CONSULTAS GENERALES
# --------------------------------------

@router.get(
    "/",
    response_model=list[MetaRespuesta]
)
def listar(
    db: SesionBD,
    usuario: UsuarioActual
):
    return consultar_metas(
        db,
        usuario.id_usuario
    )


@router.post(
    "/",
    response_model=MetaRespuesta,
    status_code=status.HTTP_201_CREATED
)
def crear(
    datos: MetaCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return crear_meta(
        db,
        usuario.id_usuario,
        datos
    )


# Esta ruta debe quedar antes de
# las rutas que utilizan {id_meta}.
@router.get(
    "/reservas/cuentas",
    response_model=list[SaldoReservaCuentaRespuesta]
)
def saldos_con_reservas(
    db: SesionBD,
    usuario: UsuarioActual
):
    return consultar_saldos_reservados(
        db,
        usuario.id_usuario
    )


# --------------------------------------
# RESERVAS Y LIBERACIONES
# --------------------------------------

@router.get(
    "/{id_meta}/reservas",
    response_model=DetalleReservasMetaRespuesta
)
def detalle_reservas(
    id_meta: int,
    db: SesionBD,
    usuario: UsuarioActual
):
    return consultar_detalle_reservas(
        db,
        usuario.id_usuario,
        id_meta
    )


@router.post(
    "/{id_meta}/reservas",
    response_model=OperacionReservaRespuesta,
    status_code=status.HTTP_201_CREATED
)
def reservar(
    id_meta: int,
    datos: OperacionReservaCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return reservar_dinero_meta(
        db,
        usuario.id_usuario,
        id_meta,
        datos
    )


@router.post(
    "/{id_meta}/liberaciones",
    response_model=OperacionReservaRespuesta,
    status_code=status.HTTP_201_CREATED
)
def liberar(
    id_meta: int,
    datos: OperacionReservaCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return liberar_dinero_meta(
        db,
        usuario.id_usuario,
        id_meta,
        datos
    )


# --------------------------------------
# FUNCIONES EXISTENTES DE METAS
# --------------------------------------

@router.get(
    "/{id_meta}",
    response_model=MetaRespuesta
)
def detalle(
    id_meta: int,
    db: SesionBD,
    usuario: UsuarioActual
):
    return consultar_meta(
        db,
        usuario.id_usuario,
        id_meta
    )


@router.patch(
    "/{id_meta}",
    response_model=MetaRespuesta
)
def editar(
    id_meta: int,
    datos: MetaActualizar,
    db: SesionBD,
    usuario: UsuarioActual
):
    return actualizar_meta(
        db,
        usuario.id_usuario,
        id_meta,
        datos
    )


# Ruta del paso 25.
# Se conserva temporalmente para mantener
# compatibilidad con la PWA actual.
#
# En 25.1B reemplazaremos este flujo por
# reservas vinculadas a cuentas.
@router.post(
    "/{id_meta}/aportes",
    response_model=MetaAporteRespuesta
)
def aportar(
    id_meta: int,
    datos: MetaAporteCrear,
    db: SesionBD,
    usuario: UsuarioActual
):
    return registrar_aporte_meta(
        db,
        usuario.id_usuario,
        id_meta,
        datos
    )


@router.post(
    "/{id_meta}/desactivar",
    response_model=MetaRespuesta
)
def desactivar(
    id_meta: int,
    db: SesionBD,
    usuario: UsuarioActual
):
    return desactivar_meta(
        db,
        usuario.id_usuario,
        id_meta
    )
