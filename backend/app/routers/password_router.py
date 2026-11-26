from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Response,
)

from fastapi.exceptions import (
    RequestValidationError,
)

from fastapi.routing import APIRoute

from app.dependencies import (
    SesionBD,
    UsuarioActual,
)

from app.schemas.password_schema import (
    SolicitudRecuperacion,
    CambioContrasena,
    RestablecimientoContrasena,
)

from app.business import (
    password_service as servicio,
)


class RutaPrivada(APIRoute):

    def get_route_handler(self):

        original = super().get_route_handler()

        async def handler(request):

            try:

                return await original(request)

            except RequestValidationError:

                raise HTTPException(
                    422,

                    "Revisa los datos ingresados.",
                ) from None

        return handler


router = APIRouter(
    route_class=RutaPrivada
)


@router.post(
    "/solicitar-recuperacion",

    status_code=202,
)
def solicitar(
    datos: SolicitudRecuperacion,

    db: SesionBD,

    tareas: BackgroundTasks,

    response: Response,
):

    tarea = servicio.solicitar_recuperacion(
        db,

        str(datos.email),
    )

    if tarea is not None:

        tareas.add_task(tarea)

    response.headers["Cache-Control"] = "no-store"

    return {
        "mensaje": (
            "Si la cuenta existe, recibiras "
            "un enlace de recuperacion."
        )
    }


@router.post("/cambiar-contrasena")
def cambiar(
    datos: CambioContrasena,

    db: SesionBD,

    usuario: UsuarioActual,

    response: Response,
):

    servicio.cambiar_contrasena(
        db,

        usuario.id_usuario,

        usuario.version_sesion,

        datos,
    )

    response.headers["Cache-Control"] = "no-store"

    return {
        "mensaje": (
            "Contrasena actualizada. "
            "Inicia sesion nuevamente."
        )
    }


@router.post("/restablecer-contrasena")
def restablecer(
    datos: RestablecimientoContrasena,

    db: SesionBD,

    response: Response,
):

    servicio.restablecer_contrasena(
        db,

        datos,
    )

    response.headers["Cache-Control"] = "no-store"

    return {
        "mensaje": (
            "Contrasena actualizada. "
            "Inicia sesion nuevamente."
        )
    }   