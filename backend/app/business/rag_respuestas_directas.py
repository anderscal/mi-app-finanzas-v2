
"""Respuestas deterministas de respaldo para preguntas sobre obligaciones.

Usa exclusivamente las obligaciones que PostgreSQL entregó para el
usuario autenticado. No consulta Gemini ni modifica datos.
"""

from decimal import Decimal, InvalidOperation
import unicodedata


CERO = Decimal("0.00")


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())

    return "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


def detectar_consulta_obligaciones(
    pregunta: str,
) -> tuple[bool, bool]:
    """Detecta solicitudes de deudas saldadas y dinero por cobrar."""

    if not isinstance(pregunta, str):
        return False, False

    texto = _normalizar(pregunta)

    pide_saldadas = (
        any(
            palabra in texto
            for palabra in (
                "deuda",
                "obligacion",
                "prestamo",
            )
        )
        and any(
            palabra in texto
            for palabra in (
                "saldad",
                "pagad",
            )
        )
        and any(
            palabra in texto
            for palabra in (
                "cuant",
                "numero",
                "cantidad",
            )
        )
    )

    pide_por_cobrar = (
        any(
            expresion in texto
            for expresion in (
                "me deben",
                "me adeudan",
                "por cobrar",
                "deben devolverme",
                "me deben pagar",
            )
        )
        and any(
            palabra in texto
            for palabra in (
                "cuanto",
                "dinero",
                "total",
                "saldo",
                "monto",
            )
        )
    )

    return pide_saldadas, pide_por_cobrar


def _moneda(
    monto: Decimal,
    codigo: str,
) -> str:
    """Formatea importes sin utilizar números de punto flotante."""

    valor = monto.quantize(Decimal("0.01"))

    entero, decimales = f"{valor:,.2f}".split(".")

    entero = entero.replace(",", ".")

    sufijo = (
        ""
        if decimales == "00"
        else f",{decimales}"
    )

    return f"${entero}{sufijo} {codigo}"


def respuesta_obligaciones(
    pregunta: str,
    obligaciones: list[dict],
    moneda: str = "COP",
) -> str | None:
    """Responde preguntas inequívocas utilizando datos SQL completos.

    No se deben pasar listas truncadas. El router obtiene
    todas las obligaciones mediante consultar_planificacion,
    usando el identificador del usuario autenticado.

    Si la evidencia contiene valores inconsistentes,
    no se genera una respuesta calculada.
    """

    saldadas, por_cobrar = detectar_consulta_obligaciones(
        pregunta
    )

    if not (saldadas or por_cobrar):
        return None

    if not isinstance(obligaciones, list):
        return None

    numero_saldadas = 0
    total_por_cobrar = CERO
    cobros_activos = 0

    for obligacion in obligaciones:

        if not isinstance(obligacion, dict):
            return None

        tipo = obligacion.get("tipo_obligacion")
        estado = obligacion.get("estado")

        if tipo not in (
            "POR_PAGAR",
            "POR_COBRAR",
        ):
            return None

        if estado not in (
            "ACTIVA",
            "SALDADA",
            "INACTIVA",
        ):
            return None

        try:
            pendiente = Decimal(
                str(obligacion["monto_pendiente"])
            )

        except (
            KeyError,
            ValueError,
            TypeError,
            InvalidOperation,
        ):
            return None

        if not pendiente.is_finite():
            return None

        if pendiente < CERO:
            return None

        if (
            estado == "SALDADA"
            and pendiente != CERO
        ):
            return None

        # Deudas propias completamente pagadas.
        if (
            tipo == "POR_PAGAR"
            and estado == "SALDADA"
        ):
            numero_saldadas += 1

        # Dinero pendiente que otras personas
        # deben devolver al usuario.
        if (
            tipo == "POR_COBRAR"
            and estado == "ACTIVA"
            and pendiente > CERO
        ):
            total_por_cobrar += pendiente
            cobros_activos += 1

    lineas = [
        (
            "**Gemini no pudo completar la consulta.** "
            "Esta es una respuesta calculada "
            "directamente desde PostgreSQL "
            "(no generada por Gemini)."
        )
    ]

    if saldadas:
        lineas.append(
            f"**Deudas tuyas saldadas:** "
            f"{numero_saldadas}. "
            "Se cuentan obligaciones POR_PAGAR "
            "con estado SALDADA."
        )

    if por_cobrar:
        lineas.append(
            "**Dinero que te deben actualmente:** "
            f"{_moneda(total_por_cobrar, moneda)}. "
            f"Corresponde a {cobros_activos} "
            "obligación(es) POR_COBRAR "
            "activa(s) con saldo pendiente."
        )

    lineas.append(
        "**Fuente:** PostgreSQL, obligaciones "
        "actuales del usuario. "
        "Los cálculos no se limitan al mes "
        "mostrado en el contexto. "
        "No incluyen operaciones offline "
        "que aún no se hayan sincronizado."
    )

    return "\n\n".join(lineas)
