
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ObligacionCrear(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    nombre_obligacion: str = Field(
        min_length=1,
        max_length=80
    )

    tipo_obligacion: Literal[
        "POR_PAGAR",
        "POR_COBRAR"
    ]

    monto_original: Decimal = Field(
        gt=Decimal("0"),
        max_digits=15,
        decimal_places=2
    )

    fecha_inicio: date

    fecha_vencimiento: date | None = None

    descripcion: str | None = Field(
        default=None,
        max_length=255
    )

    # Movimiento de dinero al crear la obligación.
    registrar_movimiento_inicial: bool = False

    # Obligatorios únicamente si hubo dinero.
    id_cuenta_inicial: int | None = Field(
        default=None,
        gt=0
    )

    uuid_local_inicial: UUID | None = None

    # Opcional para salidas de dinero.
    aplica_gmf_inicial: bool = False

    @field_validator("nombre_obligacion")
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
        return valor.strip() or None if valor is not None else None

    @model_validator(mode="after")
    def validar_reglas(self):
        if self.fecha_inicio > date.today():
            raise ValueError(
                "La fecha de inicio no puede ser futura"
            )

        if (
            self.fecha_vencimiento is not None
            and self.fecha_vencimiento < self.fecha_inicio
        ):
            raise ValueError(
                "El vencimiento no puede ser anterior al inicio"
            )

        if self.registrar_movimiento_inicial:
            if (
                self.id_cuenta_inicial is None
                or self.uuid_local_inicial is None
            ):
                raise ValueError(
                    "Debes indicar cuenta y UUID "
                    "para registrar dinero inicial"
                )

            if (
                self.tipo_obligacion == "POR_PAGAR"
                and self.aplica_gmf_inicial
            ):
                raise ValueError(
                    "El GMF inicial solo aplica a "
                    "la salida de dinero prestado"
                )

        else:
            if (
                self.id_cuenta_inicial is not None
                or self.uuid_local_inicial is not None
                or self.aplica_gmf_inicial
            ):
                raise ValueError(
                    "No puedes indicar datos de movimiento "
                    "si no hubo dinero inicial"
                )

        return self


class ObligacionActualizar(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True
    )

    nombre_obligacion: str | None = Field(
        default=None,
        min_length=1,
        max_length=80
    )

    fecha_vencimiento: date | None = None

    descripcion: str | None = Field(
        default=None,
        max_length=255
    )

    @field_validator("nombre_obligacion")
    @classmethod
    def validar_nombre(
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
        return valor.strip() or None if valor is not None else None


class ObligacionRespuesta(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id_obligacion: int
    id_usuario: int
    nombre_obligacion: str

    tipo_obligacion: Literal[
        "POR_PAGAR",
        "POR_COBRAR"
    ]

    monto_original: Decimal
    fecha_inicio: date
    fecha_vencimiento: date | None
    descripcion: str | None

    estado: Literal[
        "ACTIVA",
        "INACTIVA",
        "SALDADA"
    ]
