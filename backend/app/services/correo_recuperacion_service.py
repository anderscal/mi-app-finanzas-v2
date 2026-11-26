import os
import json

from http.client import (
    HTTPSConnection,
    HTTPException,
)

from urllib.parse import (
    urlsplit,
    quote,
)


class CorreoNoDisponible(Exception):

    pass


def obtener_configuracion():

    if os.getenv(
        "RECUPERACION_HABILITADA", "0"
    ) != "1":

        raise CorreoNoDisponible()

    clave = os.getenv(
        "BREVO_API_KEY", ""
    ).strip()

    remitente = os.getenv(
        "BREVO_REMITENTE", ""
    ).strip()

    origen = os.getenv(
        "PWA_ORIGEN", ""
    ).strip().rstrip("/")

    try:

        url = urlsplit(origen)

        puerto = url.port

        if (
            not clave
            or not remitente
            or not url.hostname
            or url.username
            or url.password
            or url.path
            or url.query
            or url.fragment
            or puerto == 0

            or any(
                c.isspace() for c in origen
            )

            or not (
                url.scheme == "https"

                or (
                    url.scheme == "http"

                    and url.hostname in {
                        "localhost",
                        "127.0.0.1",
                        "::1",
                    }
                )
            )
        ):

            raise CorreoNoDisponible()

    except ValueError as error:

        raise CorreoNoDisponible() from error

    return clave, remitente, origen


def enviar_enlace(config, email, token):

    clave, remitente, origen = config

    enlace = (
        origen
        + "/#/restablecer-contrasena?token="
        + quote(token, safe="")
    )

    datos = {
        "sender": {
            "name": "Finanzas Personales",
            "email": remitente,
        },

        "to": [
            {"email": email}
        ],

        "subject": "Restablece tu contrasena",

        "textContent": (
            "Abre este enlace para restablecer "
            "tu contrasena:\n"
            + enlace
            + "\n\nCaduca en 15 minutos. "
            "Si no solicitaste el cambio, "
            "ignora este mensaje."
        ),
    }

    conexion = HTTPSConnection(
        "api.brevo.com",
        timeout=8,
    )

    try:

        conexion.request(
            "POST",

            "/v3/smtp/email",

            json.dumps(datos).encode("utf-8"),

            {
                "api-key": clave,

                "Content-Type": "application/json",

                "Accept": "application/json",
            },
        )

        respuesta = conexion.getresponse()

        if respuesta.status != 201:

            raise CorreoNoDisponible()

    except (
        OSError,
        HTTPException,
    ) as error:

        raise CorreoNoDisponible() from error

    finally:

        conexion.close()