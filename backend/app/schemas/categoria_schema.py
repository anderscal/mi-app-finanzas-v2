from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class CategoriaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_categoria: str = Field(min_length=1, max_length=60)

    tipo_categoria: Literal["GASTO", "INGRESO"]

    @field_validator("nombre_categoria")
    @classmethod
    def normalizar_nombre(cls, valor: str) -> str:
        nombre = " ".join(valor.split())

        if not nombre:
            raise ValueError("El nombre no puede estar vacío")

        return nombre


class CategoriaActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_categoria: str = Field(
        min_length=1,
        max_length=60
    )

    @field_validator("nombre_categoria")
    @classmethod
    def normalizar_nombre(cls, valor: str) -> str:
        nombre = " ".join(valor.split())

        if not nombre:
            raise ValueError(
                "El nombre no puede estar vacío"
            )

        return nombre


class CategoriaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_categoria: int
    id_usuario: int | None
    nombre_categoria: str
    tipo_categoria: Literal["GASTO", "INGRESO"]
    es_sistema: bool
    estado: Literal["ACTIVA", "INACTIVA"]
