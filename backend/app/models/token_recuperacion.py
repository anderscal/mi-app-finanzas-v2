
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class TokenRecuperacion(Base):
    __tablename__ = "token_recuperacion"

    id_token: Mapped[int] = mapped_column(
        Integer, Identity(always=True), primary_key=True
    )

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False
    )

    token_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )

    fecha_expiracion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    usado: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
