
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AporteMeta(Base):
    __tablename__ = "aporte_meta"

    __table_args__ = (
        UniqueConstraint(
            "uuid_operacion",
            name="uq_aporte_meta_uuid"
        ),

        CheckConstraint(
            "monto > 0",
            name="ck_aporte_meta_monto"
        ),

        CheckConstraint(
            "tipo IN ('RESERVA', 'LIBERACION')",
            name="ck_aporte_meta_tipo"
        ),

        CheckConstraint(
            "estado = 'ACTIVO'",
            name="ck_aporte_meta_estado"
        ),

        Index(
            "ix_aporte_meta_usuario_cuenta",
            "id_usuario",
            "id_cuenta"
        ),

        Index(
            "ix_aporte_meta_usuario_meta",
            "id_usuario",
            "id_meta"
        ),
    )

    id_aporte: Mapped[int] = mapped_column(
        Integer,
        Identity(always=True),
        primary_key=True
    )

    uuid_operacion: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False
    )

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id_usuario"),
        nullable=False
    )

    id_meta: Mapped[int] = mapped_column(
        ForeignKey("meta_financiera.id_meta"),
        nullable=False
    )

    id_cuenta: Mapped[int] = mapped_column(
        ForeignKey("cuenta_financiera.id_cuenta"),
        nullable=False
    )

    tipo: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    monto: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )

    fecha_operacion: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    estado: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="ACTIVO"
    )

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
