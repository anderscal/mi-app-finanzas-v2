
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UsuarioRegistro(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre_1: str = Field(min_length=1, max_length=50)
    nombre_2: str | None = Field(default=None, max_length=50)
    apellido_1: str = Field(min_length=1, max_length=50)
    apellido_2: str | None = Field(default=None, max_length=50)

    email: EmailStr

    password: str = Field(min_length=12, max_length=128)


class UsuarioRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    nombre_1: str
    nombre_2: str | None
    apellido_1: str
    apellido_2: str | None
    email: EmailStr


class TokenRespuesta(BaseModel):
    access_token: str
    token_type: str = "bearer"
