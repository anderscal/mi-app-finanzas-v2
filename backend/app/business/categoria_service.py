from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.schemas.categoria_schema import CategoriaCrear
from app.schemas.categoria_schema import CategoriaActualizar

from app.models import (
    Usuario,
    CategoriaMovimiento,
)

from app.persistence.categoria_repository import (
    categorias_visibles,
    buscar_categoria_duplicada,
    insertar_categoria,
    obtener_categoria_administrable,
)

def consultar_categorias(db: Session, id_usuario: int, tipo: str | None = None):
    return categorias_visibles(db=db, id_usuario=id_usuario, tipo=tipo)


def crear_categoria_financiera(db: Session, id_usuario: int, datos: CategoriaCrear):
    try:
        # Serializar creaciones del mismo usuario
        # para reducir duplicaciones concurrentes.
        usuario = db.scalar(
            select(Usuario).where(Usuario.id_usuario == id_usuario).with_for_update()
        )

        if usuario is None:
            raise HTTPException(status_code=401, detail="Usuario no válido")

        existente = buscar_categoria_duplicada(
            db=db,
            id_usuario=id_usuario,
            nombre=datos.nombre_categoria,
            tipo=datos.tipo_categoria,
        )

        if existente is not None:
            raise HTTPException(
                status_code=409,
                detail=("Ya existe una categoría " "con ese nombre y tipo"),
            )

        categoria = CategoriaMovimiento(
            id_usuario=id_usuario,
            nombre_categoria=datos.nombre_categoria,
            tipo_categoria=datos.tipo_categoria,
            es_sistema=False,
            estado="ACTIVA",
        )

        insertar_categoria(db=db, categoria=categoria)

        db.commit()
        db.refresh(categoria)

        return categoria

    except Exception:
        db.rollback()
        raise


def _obtener_categoria_personal_bloqueada(
    db: Session, id_usuario: int, id_categoria: int
):
    # Utilizar el mismo orden de bloqueo que
    # la creación de categorías: primero usuario.
    usuario = db.scalar(
        select(Usuario).where(Usuario.id_usuario == id_usuario).with_for_update()
    )

    if usuario is None:
        raise HTTPException(status_code=401, detail="Usuario no válido")

    categoria = obtener_categoria_administrable(
        db=db, id_usuario=id_usuario, id_categoria=id_categoria
    )

    if categoria is None:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    if categoria.es_sistema:
        raise HTTPException(
            status_code=403, detail=("No puedes modificar categorías " "del sistema")
        )

    if categoria.id_usuario != id_usuario:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    return categoria

def actualizar_categoria_financiera(
    db: Session,
    id_usuario: int,
    id_categoria: int,
    datos: CategoriaActualizar
):
    try:
        categoria = _obtener_categoria_personal_bloqueada(
            db=db,
            id_usuario=id_usuario,
            id_categoria=id_categoria
        )

        if categoria.estado != "ACTIVA":
            raise HTTPException(
                status_code=409,
                detail=(
                    "No puedes editar una categoría inactiva"
                )
            )

        existente = buscar_categoria_duplicada(
            db=db,
            id_usuario=id_usuario,
            nombre=datos.nombre_categoria,
            tipo=categoria.tipo_categoria,
            id_excluir=id_categoria
        )

        if existente is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ya existe otra categoría "
                    "con ese nombre y tipo"
                )
            )

        categoria.nombre_categoria = (
            datos.nombre_categoria
        )

        db.commit()
        db.refresh(categoria)

        return categoria

    except Exception:
        db.rollback()
        raise

def desactivar_categoria_financiera(
    db: Session,
    id_usuario: int,
    id_categoria: int
):
    try:
        categoria = _obtener_categoria_personal_bloqueada(
            db=db,
            id_usuario=id_usuario,
            id_categoria=id_categoria
        )

        if categoria.estado not in (
            "ACTIVA",
            "INACTIVA"
        ):
            raise HTTPException(
                status_code=409,
                detail="Estado de categoría no válido"
            )

        if categoria.estado == "ACTIVA":
            categoria.estado = "INACTIVA"

        db.commit()
        db.refresh(categoria)

        return categoria

    except Exception:
        db.rollback()
        raise
