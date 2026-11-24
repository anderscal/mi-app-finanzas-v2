"""Gateway REST Gemini. Services.

Planificacion mediante function calling.
Generacion posterior con evidencia.
Sin dependencias de Business o Persistence.
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
TIMEOUT_INTENTO = 10.0
PRESUPUESTO_SEGUNDOS = 24.0

ESPERAS_SEGUNDOS = (1.0, 2.0)

CODIGOS_REINTENTABLES = {
    500, 502, 503, 504,
}

logger = logging.getLogger(__name__)


class IANoDisponible(Exception):

    def __init__(
        self,
        mensaje,
        codigo_http=503,
        transitorio=False,
    ):

        super().__init__(mensaje)

        self.codigo_http = codigo_http
        self.transitorio = transitorio


def modelo_gemini():

    modelo = os.getenv(
        "GEMINI_RAG_MODEL",
        MODELO_PREDETERMINADO,
    ).strip()

    if not re.fullmatch(
        r"gemini-[A-Za-z0-9._-]+",
        modelo,
    ):

        raise IANoDisponible(
            "El modelo Gemini configurado no es válido."
        )

    return modelo


def comprobar_configuracion():

    if os.getenv("RAG_IA_HABILITADA", "0") != "1":

        raise IANoDisponible(
            "El asistente de inteligencia artificial "
            "no está habilitado."
        )

    if not os.getenv("GEMINI_API_KEY", "").strip():

        raise IANoDisponible(
            "El proveedor de inteligencia artificial "
            "no está configurado."
        )

    return modelo_gemini()


def _solicitar_gemini(
    solicitud,
    modelo,
    limite_global=None,
):

    inicio = time.monotonic()

    limite = inicio + PRESUPUESTO_SEGUNDOS

    if limite_global is not None:

        limite = min(
            limite,
            limite_global,
        )

    causa = "tiempo disponible agotado"
    realizados = 0

    for intento in range(1, MAX_INTENTOS + 1):

        restante = limite - time.monotonic()

        if restante <= 0:
            break

        realizados = intento

        try:

            with urlopen(
                solicitud,
                timeout=min(
                    TIMEOUT_INTENTO,
                    restante,
                ),
            ) as respuesta:

                contenido = respuesta.read()

            if time.monotonic() >= limite:

                raise IANoDisponible(
                    "Gemini superó el tiempo disponible.",
                    transitorio=True,
                )

            resultado = json.loads(
                contenido.decode("utf-8")
            )

            if not isinstance(resultado, dict):

                raise IANoDisponible(
                    "Gemini devolvió una respuesta inválida.",
                    codigo_http=502,
                )

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

            if codigo == 429:

                raise IANoDisponible(
                    "Gemini alcanzó su cuota de solicitudes "
                    "o tokens. Intenta nuevamente cuando "
                    "haya disponibilidad.",
                    codigo_http=429,
                ) from error

            if codigo in (401, 403):

                raise IANoDisponible(
                    "El proveedor rechazó las credenciales "
                    "o permisos configurados."
                ) from error

            if codigo == 404:

                raise IANoDisponible(
                    "El modelo Gemini configurado "
                    "no está disponible."
                ) from error

            if codigo not in CODIGOS_REINTENTABLES:

                raise IANoDisponible(
                    f"Gemini rechazó la solicitud "
                    f"(HTTP {codigo}).",
                    codigo_http=502,
                ) from error

            causa = f"HTTP {codigo}"

        except (
            URLError,
            TimeoutError,
            OSError,
        ):

            causa = "fallo temporal de conexión"

        except (ValueError, UnicodeError) as error:

            raise IANoDisponible(
                "Gemini devolvió JSON inválido.",
                codigo_http=502,
            ) from error

        logger.warning(
            "Gemini no disponible | modelo=%s | "
            "intento=%s | causa=%s",
            modelo,
            intento,
            causa,
        )

        if intento >= MAX_INTENTOS:
            break

        espera = ESPERAS_SEGUNDOS[intento - 1]

        if limite - time.monotonic() <= espera:
            break

        time.sleep(espera)

    raise IANoDisponible(
        (
            "No fue posible completar la consulta con "
            f"Gemini tras {realizados} intento(s). "
            f"Motivo: {causa}. "
            "Intenta nuevamente más tarde."
        ),
        codigo_http=503,
        transitorio=True,
    )


def _enviar(cuerpo, modelo, limite_global):

    clave = os.getenv(
        "GEMINI_API_KEY", ""
    ).strip()

    if not clave:

        raise IANoDisponible(
            "Gemini no está configurado."
        )

    solicitud = Request(
        API_BASE + modelo + ":generateContent",

        data=json.dumps(
            cuerpo,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8"),

        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": clave,
        },

        method="POST",
    )

    return _solicitar_gemini(
        solicitud,
        modelo,
        limite_global,
    )


def _contenido(resultado):

    if not isinstance(resultado, dict):

        raise IANoDisponible(
            "Respuesta inválida del proveedor.",
            codigo_http=502,
        )

    candidatos = resultado.get("candidates")

    if (
        not isinstance(candidatos, list)
        or not candidatos
        or not isinstance(candidatos[0], dict)
    ):

        raise IANoDisponible(
            "Gemini no devolvió una respuesta utilizable.",
            codigo_http=502,
        )

    candidato = candidatos[0]

    motivo = candidato.get("finishReason")

    if motivo == "MAX_TOKENS":

        raise IANoDisponible(
            "Gemini alcanzó el límite de tokens de respuesta. "
            "Prueba una consulta más concreta.",
            codigo_http=502,
        )

    if motivo not in (None, "STOP"):

        raise IANoDisponible(
            "Gemini no pudo completar una respuesta válida.",
            codigo_http=502,
        )

    contenido = candidato.get("content")

    if not isinstance(contenido, dict):

        raise IANoDisponible(
            "Contenido Gemini inválido.",
            codigo_http=502,
        )

    partes = contenido.get("parts")

    if not isinstance(partes, list) or not partes:

        raise IANoDisponible(
            "Gemini devolvió una estructura inválida.",
            codigo_http=502,
        )

    if any(
        not isinstance(parte, dict)
        for parte in partes
    ):

        raise IANoDisponible(
            "Partes de respuesta Gemini inválidas.",
            codigo_http=502,
        )

    return contenido


def _extraer_texto(resultado):

    contenido = _contenido(resultado)

    textos = [
        parte["text"]

        for parte in contenido["parts"]

        if not parte.get("thought", False)

        and isinstance(
            parte.get("text"), str
        )

        and parte["text"].strip()
    ]

    texto = "\n".join(textos).strip()

    if not texto:

        raise IANoDisponible(
            "Gemini no devolvió texto utilizable.",
            codigo_http=502,
        )

    return texto


def planificar(
    pregunta,
    catalogo,
    herramienta,
    instrucciones,
    modelo,
    limite_global,
):

    usuario = {
        "role": "user",
        "parts": [{
            "text": json.dumps(
                {
                    "pregunta": pregunta,
                    "catalogo": catalogo,
                },
                ensure_ascii=False,
            ),
        }],
    }

    sistema = {
        "parts": [{
            "text": instrucciones,
        }],
    }

    herramientas = [{
        "functionDeclarations": [
            herramienta
        ],
    }]

    cuerpo = {
        "systemInstruction": sistema,

        "contents": [usuario],

        "tools": herramientas,

        "toolConfig": {
            "functionCallingConfig": {
                "mode": "ANY",
                "allowedFunctionNames": [
                    herramienta["name"]
                ],
            },
        },

        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 3072,
        },
    }

    resultado = _enviar(
        cuerpo,
        modelo,
        limite_global,
    )

    contenido = _contenido(resultado)

    llamadas = [
        parte["functionCall"]

        for parte in contenido["parts"]

        if "functionCall" in parte
    ]

    if (
        len(llamadas) != 1
        or not isinstance(llamadas[0], dict)
    ):

        raise IANoDisponible(
            "Gemini no produjo un plan de consulta único.",
            codigo_http=502,
        )

    llamada = llamadas[0]

    if (
        llamada.get("name") != herramienta["name"]

        or not isinstance(
            llamada.get("args"), dict
        )
    ):

        raise IANoDisponible(
            "Gemini solicitó una herramienta no autorizada.",
            codigo_http=502,
        )

    return {
        "modelo": modelo,
        "argumentos": llamada["args"],
        "llamada": llamada,
        "usuario": usuario,

        # Se conserva el contenido original del modelo,
        # incluyendo firmas de razonamiento cuando existan.

        "contenido_modelo": {
            **contenido,
            "role": "model",
        },

        "sistema": sistema,
        "herramientas": herramientas,
    }


def responder_con_evidencia(
    sesion,
    evidencia,
    limite_global,
):

    respuesta_funcion = {
        "name": sesion["llamada"]["name"],

        "response": {
            "resultados": evidencia,
        },
    }

    if isinstance(
        sesion["llamada"].get("id"),
        str,
    ):

        respuesta_funcion["id"] = (
            sesion["llamada"]["id"]
        )

    cuerpo = {
        "systemInstruction": sesion["sistema"],

        "contents": [
            sesion["usuario"],

            sesion["contenido_modelo"],

            {
                "role": "user",

                "parts": [{
                    "functionResponse": (
                        respuesta_funcion
                    ),
                }],
            },
        ],

        "tools": sesion["herramientas"],

        "toolConfig": {
            "functionCallingConfig": {
                "mode": "NONE",
            },
        },

        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
        },
    }

    resultado = _enviar(
        cuerpo,
        sesion["modelo"],
        limite_global,
    )

    contenido = _contenido(resultado)

    if any(
        "functionCall" in parte
        for parte in contenido["parts"]
    ):

        raise IANoDisponible(
            "Gemini solicitó operaciones adicionales "
            "fuera del límite permitido.",
            codigo_http=502,
        )

    return _extraer_texto(resultado)


def generar_respuesta_gemini(
    pregunta,
    evidencia,
    instrucciones,
):

    # Conserva una utilidad de diagnóstico del gateway.
    # El nuevo RAG no utiliza esta función para planificar.

    modelo = comprobar_configuracion()

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

    return _extraer_texto(
        _enviar(
            cuerpo,
            modelo,
            time.monotonic() + PRESUPUESTO_SEGUNDOS,
        )
    )