
"""Verificación manual del motor RAG.

Utilizar solo con una cuenta académica de prueba.
No almacena contraseñas ni tokens JWT.
"""

import getpass
import json

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API = "http://127.0.0.1:8000"


def solicitar(
    ruta,
    metodo="POST",
    datos=None,
    token=None,
    formulario=False,
):
    encabezados = {
        "Accept": "application/json",
    }

    if formulario:
        cuerpo = urlencode(
            datos or {}
        ).encode("utf-8")

        encabezados["Content-Type"] = (
            "application/x-www-form-urlencoded"
        )

    elif datos is not None:
        cuerpo = json.dumps(
            datos,
            ensure_ascii=False,
        ).encode("utf-8")

        encabezados["Content-Type"] = (
            "application/json"
        )

    else:
        cuerpo = None

    if token:
        encabezados["Authorization"] = (
            f"Bearer {token}"
        )

    solicitud = Request(
        API + ruta,
        data=cuerpo,
        headers=encabezados,
        method=metodo,
    )

    try:
        with urlopen(
            solicitud,
            timeout=65,
        ) as respuesta:
            return json.loads(
                respuesta.read().decode("utf-8")
            )

    except HTTPError as error:
        detalle = error.read(
            1000
        ).decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"FastAPI HTTP {error.code}: {detalle}"
        ) from error

    except (URLError, TimeoutError) as error:
        raise RuntimeError(
            f"No se pudo conectar con FastAPI: {error}"
        ) from error


def main():
    print()
    print("PASO 27.1 — VERIFICACIÓN DEL MOTOR RAG")
    print("Utiliza una cuenta académica de prueba.")
    print()

    correo = input(
        "Correo de la cuenta de prueba: "
    ).strip()

    password = getpass.getpass(
        "Contraseña (oculta): "
    )

    login = solicitar(
        "/auth/login",
        datos={
            "username": correo,
            "password": password,
        },
        formulario=True,
    )

    del password

    token = login["access_token"]

    print()
    pregunta = input(
        "Escribe una pregunta financiera "
        "(Enter para usar un ejemplo): "
    ).strip()

    if not pregunta:
        pregunta = (
            "¿Cuánto dinero tengo disponible "
            "sin afectar mis metas de ahorro?"
        )

    print()
    print("1. Recuperando PostgreSQL + Fuseki...")

    contexto = solicitar(
        "/consultas/asistente/contexto",
        datos={
            "pregunta": pregunta,
        },
        token=token,
    )

    print()
    print("CONTEXTO RECUPERADO")

    print(
        json.dumps(
            contexto,
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print("Recuperación completada correctamente.")

    print()
    print(
        "La siguiente operación enviará la "
        "pregunta y el contexto recuperado "
        "a un proveedor externo de IA."
    )

    decision = input(
        "¿Autorizas esa prueba? (s/N): "
    ).strip().lower()

    if decision not in ("s", "si", "sí"):
        print()
        print(
            "Prueba terminada sin enviar "
            "información a una IA externa."
        )
        return

    print()
    print("2. Generando respuesta RAG...")

    resultado = solicitar(
        "/consultas/asistente/preguntar",
        datos={
            "pregunta": pregunta,
            "autorizo_envio_ia": True,
        },
        token=token,
    )

    print()
    print("RESPUESTA DEL ASISTENTE")
    print()

    print(resultado["respuesta"])

    print()
    print("MÉTODO:", resultado["metodo"])

    print(
        "FUENTES:",
        ", ".join(
            fuente["origen"]
            for fuente in resultado["fuentes"]
        ),
    )

    print()
    print("Verificación finalizada.")


if __name__ == "__main__":
    main()
