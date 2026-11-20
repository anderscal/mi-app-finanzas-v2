
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


router = APIRouter(
    prefix="/metas",
    tags=["Metas de ahorro"]
)


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
