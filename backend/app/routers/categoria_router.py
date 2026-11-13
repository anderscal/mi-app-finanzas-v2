from typing import Literal

from fastapi import APIRouter, status

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.categoria_schema import (
    CategoriaCrear,
    CategoriaActualizar,
    CategoriaRespuesta,
)

from app.business.categoria_service import (
    consultar_categorias,
    crear_categoria_financiera,
    actualizar_categoria_financiera,
    desactivar_categoria_financiera,
)


router = APIRouter(prefix="/categorias", tags=["Categorías financieras"])


@router.get("/", response_model=list[CategoriaRespuesta])
def listar_categorias(
    db: SesionBD,
    usuario: UsuarioActual,
    tipo: Literal["GASTO", "INGRESO"] | None = None,
):
    return consultar_categorias(db=db, id_usuario=usuario.id_usuario, tipo=tipo)


@router.post(
    "/", response_model=CategoriaRespuesta, status_code=status.HTTP_201_CREATED
)
def crear_categoria(datos: CategoriaCrear, db: SesionBD, usuario: UsuarioActual):
    return crear_categoria_financiera(db=db, id_usuario=usuario.id_usuario, datos=datos)


@router.patch("/{id_categoria}", response_model=CategoriaRespuesta)
def actualizar_categoria(
    id_categoria: int, datos: CategoriaActualizar, db: SesionBD, usuario: UsuarioActual
):
    return actualizar_categoria_financiera(
        db=db, id_usuario=usuario.id_usuario, id_categoria=id_categoria, datos=datos
    )


@router.post("/{id_categoria}/desactivar", response_model=CategoriaRespuesta)
def desactivar_categoria(id_categoria: int, db: SesionBD, usuario: UsuarioActual):
    return desactivar_categoria_financiera(
        db=db, id_usuario=usuario.id_usuario, id_categoria=id_categoria
    )
