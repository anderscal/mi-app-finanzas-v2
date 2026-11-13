from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import CategoriaMovimiento


def categorias_visibles(db: Session, id_usuario: int, tipo: str | None = None):
    acceso = or_(
        and_(
            CategoriaMovimiento.es_sistema.is_(True),
            CategoriaMovimiento.id_usuario.is_(None),
        ),
        and_(
            CategoriaMovimiento.es_sistema.is_(False),
            CategoriaMovimiento.id_usuario == id_usuario,
        ),
    )

    consulta = select(CategoriaMovimiento).where(
        acceso, CategoriaMovimiento.estado == "ACTIVA"
    )

    if tipo is not None:
        consulta = consulta.where(CategoriaMovimiento.tipo_categoria == tipo)

    consulta = consulta.order_by(
        CategoriaMovimiento.tipo_categoria,
        CategoriaMovimiento.es_sistema.desc(),
        CategoriaMovimiento.nombre_categoria,
    )

    return list(db.scalars(consulta).all())



def buscar_categoria_duplicada(
    db: Session,
    id_usuario: int,
    nombre: str,
    tipo: str,
    id_excluir: int | None = None
):
    acceso = or_(
        and_(
            CategoriaMovimiento.es_sistema.is_(True),
            CategoriaMovimiento.id_usuario.is_(None)
        ),
        and_(
            CategoriaMovimiento.es_sistema.is_(False),
            CategoriaMovimiento.id_usuario == id_usuario
        )
    )

    nombre_normalizado = func.lower(
        func.regexp_replace(
            func.trim(
                CategoriaMovimiento.nombre_categoria
            ),
            "[[:space:]]+",
            " ",
            "g"
        )
    )

    filtros = [
        acceso,
        CategoriaMovimiento.tipo_categoria == tipo,
        nombre_normalizado == nombre.lower()
    ]

    if id_excluir is not None:
        filtros.append(
            CategoriaMovimiento.id_categoria != id_excluir
        )

    consulta = (
        select(CategoriaMovimiento)
        .where(*filtros)
        .limit(1)
    )

    return db.scalar(consulta)


def insertar_categoria(db: Session, categoria: CategoriaMovimiento):
    db.add(categoria)
    db.flush()

    return categoria

def obtener_categoria_administrable(
    db: Session,
    id_usuario: int,
    id_categoria: int
):
    acceso = or_(
        CategoriaMovimiento.id_usuario == id_usuario,
        and_(
            CategoriaMovimiento.es_sistema.is_(True),
            CategoriaMovimiento.id_usuario.is_(None)
        )
    )

    consulta = (
        select(CategoriaMovimiento)
        .where(
            CategoriaMovimiento.id_categoria == id_categoria,
            acceso
        )
        .with_for_update()
    )

    return db.scalar(consulta)
