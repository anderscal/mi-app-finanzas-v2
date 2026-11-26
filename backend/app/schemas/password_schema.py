from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
)


class SolicitudRecuperacion(BaseModel):

    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class NuevaContrasena(BaseModel):

    model_config = ConfigDict(extra="forbid")

    nueva_password: SecretStr = Field(
        min_length=12,
        max_length=128,
    )

    confirmacion_password: SecretStr = Field(
        min_length=12,
        max_length=128,
    )


class CambioContrasena(NuevaContrasena):

    password_actual: SecretStr = Field(
        min_length=1,
        max_length=128,
    )


class RestablecimientoContrasena(NuevaContrasena):

    token: str = Field(
        pattern=r"^[A-Za-z0-9_-]{43}$"
    )