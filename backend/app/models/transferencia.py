
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Identity, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Transferencia(Base):
    __tablename__ = "transferencia"

    id_transferencia: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )

    id_cuenta_origen: Mapped[int] = mapped_column(
        ForeignKey("cuenta_financiera.id_cuenta"),
        nullable=False
    )

    id_cuenta_destino: Mapped[int] = mapped_column(
        ForeignKey("cuenta_financiera.id_cuenta"),
        nullable=False
    )

    monto: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )

    fecha_transferencia: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    motivo: Mapped[str] = mapped_column(
        String(150), nullable=False
    )

    estado: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
