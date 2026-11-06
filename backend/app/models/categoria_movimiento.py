from sqlalchemy import Boolean, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CategoriaMovimiento(Base):
    __tablename__ = "categoria_movimiento"

    id_categoria: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )

    id_usuario: Mapped[int | None] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=True
    )

    nombre_categoria: Mapped[str] = mapped_column(
        String(60), nullable=False
    )

    tipo_categoria: Mapped[str] = mapped_column(
        String(10), nullable=False
    )

    es_sistema: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )

    estado: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
