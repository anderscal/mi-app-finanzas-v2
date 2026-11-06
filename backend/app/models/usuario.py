
from __future__ import annotations

from sqlalchemy import Integer, String, Identity
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[int] = mapped_column(
        Integer,
        Identity(always=True),
        primary_key=True
    )

    nombre_1: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    nombre_2: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    apellido_1: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    apellido_2: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    email: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    cuentas: Mapped[list[CuentaFinanciera]] = relationship(
        back_populates="usuario"
    )
