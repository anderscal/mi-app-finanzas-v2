
"""Gateway de Google Gemini. Capa Services.

No consulta PostgreSQL ni Fuseki.
No importa Business.
Valida la estructura de las respuestas externas.
"""

import json
import logging
import os
import re
import time

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/"
)

MODELO_PREDETERMINADO = "gemini-2.5-flash-lite"

MAX_INTENTOS = 3
PRESUPUESTO_SEGUNDOS = 24.0
TIMEOUT_INTENTO = 10.0
ESPERAS_SEGUNDOS = (1.0, 2.0)

CODIGOS_REINTENTABLES = {
    500, 502, 503, 504,
}

logger = logging.getLogger(__name__)


class IANoDisponible(Exception):

    def __init__(
        self,
        mensaje: str,
        codigo_http: int = 503,
        transitorio: bool = False,
    ):
        super().__init__(mensaje)
        self.codigo_http = codigo_http
        self.transitorio = transitorio


def modelo_gemini() -> str:

    modelo = os.getenv(
        "GEMINI_RAG_MODEL",
        MODELO_PREDETERMINADO,
    ).strip()

    if not re.fullmatch(
        r"gemini-[A-Za-z0-9._-]+",
        modelo,
    ):
        raise IANoDisponible(
            "El nombre del modelo Gemini "
            "no tiene un formato válido."
        )

    return modelo


def _fallo_temporal(intentos, causa):

    return IANoDisponible(
        (
            "Gemini no pudo completar la consulta "
            f"tras {intentos} intento(s). "
            f"Motivo: {causa}. "
            "Intenta nuevamente más tarde."
        ),
        codigo_http=503,
        transitorio=True,
    )


def _solicitar_gemini(
    solicitud: Request,
    modelo: str,
) -> dict:

    inicio = time.monotonic()
    limite = inicio + PRESUPUESTO_SEGUNDOS

    causa = "presupuesto temporal agotado"
    realizados = 0

    for intento in range(1, MAX_INTENTOS + 1):

        restante = limite - time.monotonic()

        if restante <= 0:
            break

        timeout = min(
            TIMEOUT_INTENTO,
            restante,
        )

        realizados = intento

        try:

            with urlopen(
                solicitud,
                timeout=timeout,
            ) as respuesta:

                resultado = json.loads(
                    respuesta.read().decode("utf-8")
                )

            if time.monotonic() >= limite:

                raise _fallo_temporal(
                    realizados,
                    "presupuesto temporal agotado",
                )

            if not isinstance(resultado, dict):
                raise ValueError("JSON inválido")

            logger.info(
                "Gemini respondió | modelo=%s | "
                "intentos=%s | segundos=%.2f",
                modelo,
                realizados,
                time.monotonic() - inicio,
            )

            return resultado

        except HTTPError as error:

            codigo = error.code
            error.close()

            if codigo in CODIGOS_REINTENTABLES:

                causa = f"HTTP {codigo}"

                logger.warning(
                    "Gemini HTTP %s | modelo=%s | "
                    "intento=%s/%s | segundos=%.2f",
                    codigo,
                    modelo,
                    intento,
                    MAX_INTENTOS,
                    time.monotonic() - inicio,
                )

            elif codigo == 429:

                raise IANoDisponible(
                    "Gemini alcanzó el límite "
                    "de solicitudes o tokens.",
                    codigo_http=429,
                ) from error

            elif codigo in (401, 403):

                raise IANoDisponible(
                    "Gemini rechazó las credenciales "
                    "o los permisos del proyecto."
                ) from error

            elif codigo == 404:

                raise IANoDisponible(
                    "El modelo Gemini configurado "
                    "no está disponible en esta API. "
                    "Revisa GEMINI_RAG_MODEL."
                ) from error

            else:

                raise IANoDisponible(
                    "Gemini no pudo completar "
                    f"la solicitud (HTTP {codigo})."
                ) from error

        except (
            URLError,
            TimeoutError,
            OSError,
        ) as error:

            causa = "error temporal de conexión"

            logger.warning(
                "Conexión Gemini falló | modelo=%s | "
                "intento=%s/%s | tipo=%s",
                modelo,
                intento,
                MAX_INTENTOS,
                type(error).__name__,
            )

        except (ValueError, UnicodeError) as error:

            raise IANoDisponible(
                "Gemini devolvió una respuesta JSON inválida."
            ) from error

        if intento >= MAX_INTENTOS:
            break

        espera = ESPERAS_SEGUNDOS[intento - 1]

        restante = limite - time.monotonic()

        if restante <= espera:
            break

        time.sleep(espera)

    raise _fallo_temporal(
        realizados,
        causa,
    )


def _estructura_invalida():

    return IANoDisponible(
        "Gemini devolvió una estructura de respuesta inválida.",
        codigo_http=503,
        transitorio=True,
    )


def _extraer_texto(resultado: dict) -> str:
    """Valida el contrato externo antes de leer el texto.

    No reintenta respuestas estructuralmente invalidas.
    El controlador puede activar el respaldo local.
    """

    if not isinstance(resultado, dict):
        raise _estructura_invalida()

    candidatos = resultado.get("candidates", [])

    if not isinstance(candidatos, list):
        raise _estructura_invalida()

    if not candidatos:

        raise IANoDisponible(
            "Gemini no devolvió una respuesta utilizable."
        )

    primero = candidatos[0]

    if not isinstance(primero, dict):
        raise _estructura_invalida()

    motivo = primero.get("finishReason")

    if motivo not in (None, "STOP"):

        raise IANoDisponible(
            "Gemini no completó una respuesta válida."
        )

    contenido = primero.get("content", {})

    if not isinstance(contenido, dict):
        raise _estructura_invalida()

    partes = contenido.get("parts", [])

    if not isinstance(partes, list):
        raise _estructura_invalida()

    textos = [
        parte["text"]

        for parte in partes

        if isinstance(parte, dict)
        and not parte.get("thought", False)
        and isinstance(parte.get("text"), str)
        and parte["text"].strip()
    ]

    texto = "\n".join(textos).strip()

    if not texto:

        raise IANoDisponible(
            "Gemini no devolvió texto utilizable."
        )

    return texto


def generar_respuesta_gemini(
    pregunta: str,
    evidencia: dict,
    instrucciones: str,
) -> str:

    clave = os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()

    if not clave:

        raise IANoDisponible(
            "Falta configurar GEMINI_API_KEY "
            "en el backend."
        )

    modelo = modelo_gemini()

    cuerpo = {
        "systemInstruction": {
            "parts": [{
                "text": instrucciones,
            }],
        },

        "contents": [{
            "role": "user",
            "parts": [{
                "text": json.dumps(
                    {
                        "pregunta_usuario": pregunta,
                        "contexto_recuperado": evidencia,
                    },
                    ensure_ascii=False,
                ),
            }],
        }],

        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 900,
        },
    }

    solicitud = Request(
        API_BASE + modelo + ":generateContent",

        data=json.dumps(
            cuerpo,
            ensure_ascii=False,
        ).encode("utf-8"),

        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": clave,
        },

        method="POST",
    )

    resultado = _solicitar_gemini(
        solicitud,
        modelo,
    )

    return _extraer_texto(resultado)
