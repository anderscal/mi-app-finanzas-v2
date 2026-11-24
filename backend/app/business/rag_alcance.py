
"""Politica de alcance temporal y de entidades.

Business Layer.

No ejecuta consultas.
No depende de FastAPI ni de Gemini.
"""

import re

from datetime import date

from app.business.rag_intencion import (
    normalizar,
)


MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

NOMBRES_MESES = "|".join(MESES)

MES_EXPLICITO = (
    rf"\b({NOMBRES_MESES})"
    r"\s+(?:de\s+)?(\d{4})\b"
)

MES_RELATIVO = (
    r"\b(?:el\s+)?"
    r"(mes pasado|mes anterior|"
    r"este mes|mes actual|mes en curso)\b"
)

MENSAJE_PERIODO = (
    "No se admite ese período. "
    "Indica el mes actual, el mes pasado "
    "o un mes y año concretos."
)


class AlcanceNoAdmitido(ValueError):
    """Periodo o filtro no soportado."""


def mes_anterior(hoy: date) -> tuple[int, int]:

    if hoy.month == 1:
        return hoy.year - 1, 12

    return hoy.year, hoy.month - 1


def quitar_periodos(texto: str) -> str:

    texto = normalizar(texto)

    texto = re.sub(
        r"(?:\ben\s+)?" + MES_EXPLICITO,
        " ",
        texto,
    )

    texto = re.sub(
        r"(?:\ben\s+)?" + MES_RELATIVO,
        " ",
        texto,
    )

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


def resolver_periodo(
    pregunta: str,
    hoy: date,
) -> tuple[int, int]:

    texto = normalizar(pregunta)

    explicitos = list(
        re.finditer(
            MES_EXPLICITO,
            texto,
        )
    )

    relativos = list(
        re.finditer(
            MES_RELATIVO,
            texto,
        )
    )

    # No interpretar rangos o multiples meses
    # como si fueran un unico periodo.

    if len(explicitos) + len(relativos) > 1:

        raise AlcanceNoAdmitido(
            MENSAJE_PERIODO
        )

    restante = quitar_periodos(texto)

    # Detectar expresiones temporales fuera
    # de las capacidades mensuales actuales.

    no_admitidos = (
        rf"\b(?:{NOMBRES_MESES})\b"
        r"|\b(?:ayer|anteayer|hoy|manana|"
        r"semanas?|trimestres?|semestres?|"
        r"anos?|anual|"
        r"ultim[oa]s?|proxim[oa]s?|hace)\b"
        r"|\b(?:19|20|21)\d{2}\b"
        r"|\b\d{1,4}[-/]\d{1,2}"
        r"(?:[-/]\d{1,4})?\b"
        r"|\b(?:dia|dias|meses)\b"
        r"|\bmes\b"
    )

    if re.search(
        no_admitidos,
        restante,
    ):

        raise AlcanceNoAdmitido(
            MENSAJE_PERIODO
        )

    if explicitos or relativos:

        if re.search(
            r"\b(?:desde|hasta|entre)\b",
            restante,
        ):

            raise AlcanceNoAdmitido(
                MENSAJE_PERIODO
            )

    if explicitos:

        coincidencia = explicitos[0]

        mes = MESES[
            coincidencia.group(1)
        ]

        anio = int(
            coincidencia.group(2)
        )

        if not 2000 <= anio <= 9998:

            raise AlcanceNoAdmitido(
                MENSAJE_PERIODO
            )

        periodo = (anio, mes)

    elif relativos:

        expresion = relativos[0].group(1)

        if expresion in {
            "mes pasado",
            "mes anterior",
        }:

            periodo = mes_anterior(hoy)

        else:

            periodo = (
                hoy.year,
                hoy.month,
            )

    else:

        periodo = (
            hoy.year,
            hoy.month,
        )

    if periodo > (
        hoy.year,
        hoy.month,
    ):

        raise AlcanceNoAdmitido(
            "No se admiten períodos financieros futuros."
        )

    return periodo


def _limpiar_nombre(texto):

    return re.sub(
        r"\s+",
        " ",
        normalizar(str(texto)),
    ).strip(
        " \t¿?¡!.,;:\"'“”"
    )


REFERENCIAS_GENERALES = {
    "cuentas",
    "mis cuentas",
    "las cuentas",
    "todas las cuentas",
    "todas mis cuentas",
    "todas ellas",
    "cada cuenta",
    "que cuenta",
    "que cuentas",
    "cual cuenta",
    "cuales cuentas",
    "cual de mis cuentas",
    "cuales de mis cuentas",
    "categorias",
    "las categorias",
    "mis categorias",
    "todas las categorias",
    "cada categoria",
    "que categoria",
    "que categorias",
    "cual categoria",
    "cuales categorias",
    "que",
}


def referencia_entidad(
    pregunta: str,
    dominio: str,
) -> str | None:
    """Reconoce referencias explicitas a una entidad.

    Devuelve None cuando la consulta es general.
    No deduce identificadores a partir del nombre.
    """

    texto = _limpiar_nombre(
        quitar_periodos(pregunta)
    )

    coincidencia = re.search(
        r"\ben\s+(.+)$",
        texto,
    )

    if coincidencia is None:

        if dominio == "cuentas":

            coincidencia = re.search(
                r"\b(?:saldo(?:\s+(?:libre|"
                r"disponible|real|total|actual))?"
                r"|disponible)\s+de\s+(.+)$",
                texto,
            )

        elif dominio == "movimientos":

            coincidencia = re.search(
                r"\b(?:gasto|gastos)\s+"
                r"de\s+((?:la\s+)?"
                r"categoria\s+.+)$",
                texto,
            )

    if coincidencia is None:
        return None

    referencia = _limpiar_nombre(
        coincidencia.group(1)
    )

    if not referencia:
        return None

    if referencia in REFERENCIAS_GENERALES:
        return None

    return referencia


def resolver_entidad(
    referencia: str,
    filas: list[dict],
    campo_nombre: str,
    tipo_entidad: str,
) -> dict:

    referencia = _limpiar_nombre(
        referencia
    )

    # Primero se compara el nombre completo.
    # Asi se conservan nombres que realmente
    # empiezan por Cuenta o Categoria.

    def coincidencias(nombre):

        return [
            fila for fila in filas

            if isinstance(
                fila.get(campo_nombre),
                str,
            )

            and _limpiar_nombre(
                fila[campo_nombre]
            ) == nombre
        ]

    seleccion = coincidencias(
        referencia
    )

    if not seleccion:

        simplificada = re.sub(
            r"^(?:(?:mi|la|el)\s+)?"
            r"(?:cuenta|categoria)"
            r"\s+(?:de\s+)?",
            "",
            referencia,
        )

        if simplificada != referencia:

            seleccion = coincidencias(
                simplificada
            )

    if not seleccion:

        raise AlcanceNoAdmitido(
            f"No puedo identificar la {tipo_entidad} "
            "solicitada. No se mostrará un total "
            "general como si correspondiera a esa entidad. "
            "Indica su nombre exacto."
        )

    if len(seleccion) != 1:

        raise AlcanceNoAdmitido(
            f"No puedo identificar una única {tipo_entidad} "
            "con ese nombre. Existen varias coincidencias."
        )

    return seleccion[0]
