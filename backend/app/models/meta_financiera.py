
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Identity, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MetaFinanciera(Base):
    __tablename__ = "meta_financiera"

    id_meta: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"), nullable=False
    )

    nombre_meta: Mapped[str] = mapped_column(
        String(80), nullable=False
    )

    monto_objetivo: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )

    monto_acumulado: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )

    fecha_objetivo: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    descripcion: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    estado: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
