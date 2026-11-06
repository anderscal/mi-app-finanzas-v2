
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
class TransferenciaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uuid_operacion: UUID

    id_cuenta_origen: int = Field(gt=0)
    id_cuenta_destino: int = Field(gt=0)

    monto: Decimal = Field(
        gt=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )

    fecha_transferencia: date

    motivo: str = Field(
        default="Movimiento interno",
        min_length=1,
        max_length=150
    )

    aplica_gmf: bool = False

    @field_validator("fecha_transferencia")
    @classmethod
    def validar_fecha_transferencia(
        cls,
        valor: date
    ) -> date:
        if valor > date.today():
            raise ValueError(
                "La fecha no puede ser futura"
            )
        return valor


class TransferenciaRespuesta(BaseModel):
    id_transferencia: int
    uuid_operacion: UUID

    id_movimiento_salida: int
    id_movimiento_entrada: int

    monto: Decimal
    monto_gmf: Decimal

    creado: bool
    mensaje: str

class AbonoObligacionCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uuid_local: UUID

    id_cuenta: int = Field(gt=0)
    id_obligacion: int = Field(gt=0)

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
    def validar_fecha_abono(
        cls,
        valor: date
    ) -> date:
        if valor > date.today():
            raise ValueError(
                "La fecha no puede ser futura"
            )
        return valor


class AbonoObligacionRespuesta(BaseModel):
    id_movimiento: int
    id_obligacion: int

    uuid_local: UUID

    tipo: Literal["INGRESO", "GASTO"]

    monto: Decimal
    monto_pendiente: Decimal

    creado: bool
    mensaje: str