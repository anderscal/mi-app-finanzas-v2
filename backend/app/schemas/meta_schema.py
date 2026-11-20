
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class MetaCrear(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    nombre_meta: str = Field(
        min_length=1,
        max_length=80
    )

    monto_objetivo: Decimal = Field(
        gt=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )

    fecha_objetivo: date

    descripcion: str | None = Field(
        default=None,
        max_length=255
    )

    @field_validator("nombre_meta")
    @classmethod
    def normalizar_nombre(cls, valor: str) -> str:
        nombre = " ".join(valor.split())

        if not nombre:
            raise ValueError(
                "El nombre no puede estar vacío"
            )

        return nombre

    @field_validator("descripcion")
    @classmethod
    def normalizar_descripcion(
        cls,
        valor: str | None
    ) -> str | None:
        return (
            valor.strip() or None
            if valor is not None
            else None
        )

    @model_validator(mode="after")
    def validar_fecha(self):
        if self.fecha_objetivo < date.today():
            raise ValueError(
                "La fecha objetivo no puede ser pasada"
            )

        return self


class MetaActualizar(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    nombre_meta: str | None = Field(
        default=None,
        min_length=1,
        max_length=80
    )

    monto_objetivo: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )

    fecha_objetivo: date | None = None

    descripcion: str | None = Field(
        default=None,
        max_length=255
    )

    @field_validator("nombre_meta")
    @classmethod
    def normalizar_nombre(
        cls,
        valor: str | None
    ) -> str:
        if valor is None:
            raise ValueError(
                "El nombre no puede ser nulo"
            )

        nombre = " ".join(valor.split())

        if not nombre:
            raise ValueError(
                "El nombre no puede estar vacío"
            )

        return nombre

    @field_validator("descripcion")
    @classmethod
    def normalizar_descripcion(
        cls,
        valor: str | None
    ) -> str | None:
        return (
            valor.strip() or None
            if valor is not None
            else None
        )


class MetaAporteCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monto: Decimal = Field(
        gt=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )

    acumulado_esperado: Decimal = Field(
        ge=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )


class MetaRespuesta(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id_meta: int
    id_usuario: int
    nombre_meta: str
    monto_objetivo: Decimal
    monto_acumulado: Decimal
    fecha_objetivo: date
    descripcion: str | None

    estado: Literal[
        "ACTIVA",
        "CUMPLIDA",
        "INACTIVA"
    ]


class MetaAporteRespuesta(BaseModel):
    id_meta: int
    monto_objetivo: Decimal
    monto_acumulado: Decimal
    porcentaje_progreso: Decimal

    estado: Literal[
        "ACTIVA",
        "CUMPLIDA"
    ]

    creado: bool
    mensaje: str
