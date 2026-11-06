
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Identity, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ObligacionFinanciera(Base):
    __tablename__ = "obligacion_financiera"

    id_obligacion: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"), nullable=False
    )

    nombre_obligacion: Mapped[str] = mapped_column(
        String(80), nullable=False
    )

    tipo_obligacion: Mapped[str] = mapped_column(
        String(12), nullable=False
    )

    monto_original: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )

    fecha_inicio: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    fecha_vencimiento: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    descripcion: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    estado: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
