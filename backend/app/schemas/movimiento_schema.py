
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)


class MovimientoNormalCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uuid_local: UUID

    id_cuenta: int = Field(gt=0)

    id_categoria: int = Field(gt=0)

    tipo: Literal["INGRESO", "GASTO"]

    monto: Decimal = Field(
        gt=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )

    fecha_movimiento: date

    descripcion: str | None = Field(
        default=None,
        max_length=255
    )

    @field_validator("fecha_movimiento")
    @classmethod
    def validar_fecha(cls, valor: date) -> date:
        if valor > date.today():
            raise ValueError(
                "La fecha no puede ser futura"
            )
        return valor


class MovimientoNormalRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_movimiento: int
    uuid_local: UUID
    id_cuenta: int
    id_categoria: int
    tipo: Literal["INGRESO", "GASTO"]
    origen: Literal["NORMAL"]
    monto: Decimal
    fecha_movimiento: date
    descripcion: str | None
    estado: Literal["ACTIVO", "ANULADO"]

class RegistroMovimientoRespuesta(BaseModel):
    id_movimiento: int
    uuid_local: UUID
    tipo: Literal["INGRESO", "GASTO"]
    monto: Decimal
    creado: bool
    mensaje: str
