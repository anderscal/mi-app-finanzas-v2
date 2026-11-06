
from decimal import Decimal

from sqlalchemy import (
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    SmallInteger
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Presupuesto(Base):
    __tablename__ = "presupuesto"

    id_presupuesto: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"), nullable=False
    )

    id_categoria: Mapped[int] = mapped_column(
        ForeignKey("categoria_movimiento.id_categoria"),
        nullable=False
    )

    anio: Mapped[int] = mapped_column(
        SmallInteger, nullable=False
    )

    mes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False
    )

    monto_limite: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )
