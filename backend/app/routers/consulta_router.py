from fastapi import APIRouter, Query

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.business.movimiento_service import (
    consultar_historial_mensual,
    consultar_resumen_mensual,
)

from app.business.planificacion_service import (
    consultar_planificacion,
)


router = APIRouter(
    prefix="/consultas",
    tags=["Consultas financieras"]
)


@router.get("/resumen-mensual")
def resumen_mensual(
    db: SesionBD,
    usuario: UsuarioActual,
    anio: int = Query(
        ...,
        ge=2000,
        le=9998
    ),
    mes: int = Query(
        ...,
        ge=1,
        le=12
    )
):
    return consultar_resumen_mensual(
        db=db,
        id_usuario=usuario.id_usuario,
        anio=anio,
        mes=mes
    )


@router.get("/historial-mensual")
def historial_mensual(
    db: SesionBD,
    usuario: UsuarioActual,
    anio: int = Query(
        ...,
        ge=2000,
        le=9998
    ),
    mes: int = Query(
        ...,
        ge=1,
        le=12
    )
):
    return consultar_historial_mensual(
        db=db,
        id_usuario=usuario.id_usuario,
        anio=anio,
        mes=mes
    )


@router.get("/planificacion")
def planificacion(
    db: SesionBD,
    usuario: UsuarioActual
):
    return consultar_planificacion(
        db=db,
        id_usuario=usuario.id_usuario
    )