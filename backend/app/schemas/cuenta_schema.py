
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

class CuentaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_cuenta: str = Field(
        min_length=1,
        max_length=80
    )

    tipo_cuenta: Literal[
        "AHORROS",
        "CORRIENTE",
        "EFECTIVO"
    ]

    institucion: str | None = Field(
        default=None,
        max_length=80
    )

    saldo_inicial: Decimal = Field(
        ge=Decimal("0.00"),
        max_digits=15,
        decimal_places=2
    )

    @field_validator("nombre_cuenta")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        valor = valor.strip()

        if not valor:
            raise ValueError(
                "El nombre no puede estar vacío"
            )

        return valor

    @field_validator("institucion")
    @classmethod
    def normalizar_institucion(
        cls,
        valor: str | None
    ) -> str | None:
        if valor is None:
            return None

        return valor.strip() or None

class CuentaActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_cuenta: str | None = Field(
        default=None,
        min_length=1,
        max_length=80
    )

    institucion: str | None = Field(
        default=None,
        max_length=80
    )

    @field_validator("nombre_cuenta")
    @classmethod
    def validar_nombre(
        cls,
        valor: str | None
    ) -> str | None:
        if valor is None:
            return None

        valor = valor.strip()

        if not valor:
            raise ValueError(
                "El nombre no puede estar vacío"
            )

        return valor

    @field_validator("institucion")
    @classmethod
    def normalizar_institucion(
        cls,
        valor: str | None
    ) -> str | None:
        if valor is None:
            return None

        return valor.strip() or None

class CuentaRespuesta(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id_cuenta: int
    id_usuario: int
    nombre_cuenta: str
    tipo_cuenta: str
    institucion: str | None
    saldo_inicial: Decimal
    estado: str
