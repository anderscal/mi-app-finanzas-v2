
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class OperacionReservaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uuid_operacion: UUID

    id_cuenta: int = Field(gt=0)

    monto: Decimal = Field(
        gt=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )

    fecha_operacion: date

    @model_validator(mode="after")
    def validar_fecha(self):
        if self.fecha_operacion > date.today():
            raise ValueError(
                "La fecha de operación no puede ser futura"
            )

        return self


class EventoReservaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_aporte: int
    uuid_operacion: UUID
    id_usuario: int
    id_meta: int
    id_cuenta: int
    tipo: Literal["RESERVA", "LIBERACION"]
    monto: Decimal
    fecha_operacion: date
    estado: Literal["ACTIVO"]


class OperacionReservaRespuesta(BaseModel):
    id_aporte: int
    uuid_operacion: UUID
    id_meta: int
    id_cuenta: int
    tipo: Literal["RESERVA", "LIBERACION"]
    monto: Decimal

    monto_acumulado: Decimal
    reservado_en_cuenta: Decimal
    saldo_real: Decimal
    saldo_libre: Decimal

    creado: bool


class SaldoReservaCuentaRespuesta(BaseModel):
    id_cuenta: int
    nombre_cuenta: str
    estado: str

    saldo_real: Decimal
    monto_reservado: Decimal
    saldo_libre: Decimal


class DetalleReservasMetaRespuesta(BaseModel):
    id_meta: int
    nombre_meta: str
    monto_objetivo: Decimal
    monto_acumulado: Decimal

    monto_vinculado: Decimal
    monto_sin_vincular: Decimal

    registros: list[EventoReservaRespuesta]
