
from pydantic import BaseModel, Field, field_validator


class PreguntaRAG(BaseModel):
    pregunta: str = Field(
        min_length=5,
        max_length=400,
    )

    @field_validator("pregunta")
    @classmethod
    def limpiar_pregunta(cls, valor: str) -> str:
        valor = valor.strip()

        if len(valor) < 5:
            raise ValueError(
                "La pregunta debe tener al menos cinco caracteres"
            )

        return valor


class PreguntaConIA(PreguntaRAG):
    autorizo_envio_ia: bool = False
