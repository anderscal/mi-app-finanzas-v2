
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class CuentaFinanciera(Base):
    __tablename__ = "cuenta_financiera"

    id_cuenta: Mapped[int] = mapped_column(
        Integer,
        Identity(always=True),
        primary_key=True
    )

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False
    )

    nombre_cuenta: Mapped[str] = mapped_column(
        String(80),
        nullable=False
    )

    tipo_cuenta: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    institucion: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True
    )

    saldo_inicial: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )

    estado: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    usuario: Mapped[Usuario] = relationship(
        back_populates="cuentas"
    )
