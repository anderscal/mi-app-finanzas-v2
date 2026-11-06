
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Uuid,
    text
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Movimiento(Base):
    __tablename__ = "movimiento"

    id_movimiento: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )

    uuid_local: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        unique=True
    )

    id_cuenta: Mapped[int] = mapped_column(
        ForeignKey("cuenta_financiera.id_cuenta"),
        nullable=False
    )

    id_categoria: Mapped[int | None] = mapped_column(
        ForeignKey("categoria_movimiento.id_categoria"),
        nullable=True
    )

    id_transferencia: Mapped[int | None] = mapped_column(
        ForeignKey("transferencia.id_transferencia"),
        nullable=True
    )

    id_obligacion: Mapped[int | None] = mapped_column(
        ForeignKey("obligacion_financiera.id_obligacion"),
        nullable=True
    )

    tipo: Mapped[str] = mapped_column(
        String(10), nullable=False
    )

    origen: Mapped[str] = mapped_column(
        String(15), nullable=False
    )

    monto: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )

    fecha_movimiento: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    descripcion: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    aplica_gmf: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )

    monto_gmf: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )

    estado: Mapped[str] = mapped_column(
        String(10), nullable=False
    )

    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )
