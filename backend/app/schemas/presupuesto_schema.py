
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class PresupuestoCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_categoria: int = Field(gt=0)

    anio: int = Field(
        ge=2000,
        le=9998
    )

    mes: int = Field(
        ge=1,
        le=12
    )

    monto_limite: Decimal = Field(
        gt=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )


class PresupuestoActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monto_limite: Decimal = Field(
        gt=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )


class PresupuestoRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_presupuesto: int
    id_usuario: int
    id_categoria: int
    anio: int
    mes: int
    monto_limite: Decimal
