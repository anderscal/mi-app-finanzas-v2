
"""Operaciones colectivas sobre evidencia financiera.

Business Layer.
No consulta bases de datos ni utiliza Gemini.
"""

import operator
import re

from decimal import Decimal

from app.business.rag_intencion import normalizar
from app.business import rag_motor_respuestas as motor


MAX_LISTADO = 20
MAX_CLASIFICACION = 5

OPERADORES = {
    "igual": operator.eq,
    "mayor": operator.gt,
    "menor": operator.lt,
    "mayor_igual": operator.ge,
    "menor_igual": operator.le,
}

ETIQUETAS = {
    "saldo_real": "saldo real",
    "saldo_libre": "saldo disponible",
    "reservado": "saldo reservado",
}

PATRONES_OPERADORES = {
    "igual": r"igual(?:\s+a)?|en|de",
    "mayor": r"superior(?:es)?\s+a|mayor(?:es)?(?:\s+que|\s+a)?|mas\s+de",
    "menor": r"inferior(?:es)?\s+a|menor(?:es)?(?:\s+que|\s+a)?|menos\s+de",
    "mayor_igual": r"mayor(?:es)?\s+o\s+igual(?:es)?(?:\s+a)?|al\s+menos",
    "menor_igual": r"menor(?:es)?\s+o\s+igual(?:es)?(?:\s+a)?|como\s+maximo",
}


def _importe(texto):
    """Formato monetario colombiano.

    Ejemplos:
    50000
    50.000
    50.000,50
    cero
    """

    texto = texto.strip()

    if texto == "cero":
        return Decimal("0")

    if re.fullmatch(r"-?\d+(?:,\d{1,2})?", texto):
        return Decimal(texto.replace(",", "."))

    if re.fullmatch(
        r"-?\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?",
        texto,
    ):
        return Decimal(
            texto.replace(".", "").replace(",", ".")
        )

    raise ValueError("Formato monetario no reconocido")


def _filtro_saldo(texto):

    campo = "saldo_real"

    if re.search(
        r"\bsaldo\s+(?:disponible|libre)\b",
        texto,
    ):
        campo = "saldo_libre"

    elif re.search(
        r"\bsaldo\s+reservado\b",
        texto,
    ):
        campo = "reservado"

    if re.search(r"\bsin saldo\b", texto):

        return campo, "igual", Decimal("0")

    patron = (
        r"\bsaldo"
        r"(?:\s+(?:real|libre|disponible|reservado))?"
        r"\s+"
    )

    importe = r"(cero|-?\d+(?:[.,]\d+)*)"

    # Los operadores compuestos se evalúan primero.

    for clave in (
        "mayor_igual",
        "menor_igual",
        "mayor",
        "menor",
        "igual",
    ):

        coincidencia = re.search(
            patron
            + "(?:"
            + PATRONES_OPERADORES[clave]
            + r")\s+\$?\s*"
            + importe
            + r"(?![\d.,])",
            texto,
        )

        if coincidencia:

            return (
                campo,
                clave,
                _importe(coincidencia.group(1)),
            )

    coincidencia = re.search(
        patron + r"\$?\s*" + importe + r"(?![\d.,])",
        texto,
    )

    if coincidencia:

        return (
            campo,
            "igual",
            _importe(coincidencia.group(1)),
        )

    return None


def _bloque_limitacion(titulo, mensaje):

    return motor.Bloque(
        titulo=titulo,
        resumen=[mensaje],
    )


def _consultar_cuentas(texto, contexto):

    titulo = "Cuentas y liquidez"

    try:
        filtro = _filtro_saldo(texto)

    except ValueError:

        return _bloque_limitacion(
            titulo,
            "No puedo interpretar el importe solicitado. "
            "Indícalo en pesos colombianos.",
        )

    if filtro is None:
        return None

    campo, operacion, limite = filtro

    filas = contexto.get(
        "postgresql", {}
    ).get("cuentas")

    resumen = contexto.get(
        "analisis_financiero", {}
    ).get("cuentas", {})

    if (
        not isinstance(filas, list)
        or type(
            resumen.get("numero_cuentas_activas")
        ) is not int
        or resumen["numero_cuentas_activas"] != len(filas)
    ):

        return _bloque_limitacion(
            titulo,
            "No se recuperó evidencia suficiente "
            "para filtrar todas las cuentas activas.",
        )

    comparar = OPERADORES[operacion]

    seleccion = []

    for fila in filas:

        saldo = motor._decimal(fila.get(campo))

        if saldo is None:

            return _bloque_limitacion(
                titulo,
                "No se dispone de saldos válidos "
                "para completar este filtro.",
            )

        if comparar(saldo, limite):

            seleccion.append((fila, saldo))

    etiqueta = ETIQUETAS[campo]

    comparacion = {
        "igual": "igual a",
        "mayor": "mayor que",
        "menor": "menor que",
        "mayor_igual": "mayor o igual a",
        "menor_igual": "menor o igual a",
    }[operacion]

    criterio = (
        f"{etiqueta} {comparacion} "
        f"{motor._dinero(limite)}"
    )

    bloque = motor.Bloque(
        titulo=titulo,
        resumen=[
            f"Cuentas activas con {criterio}: "
            f"{len(seleccion)}"
        ],
    )

    contar = bool(
        re.search(
            r"\b(?:cuantas|cantidad|numero)\b",
            texto,
        )
    )

    listar = bool(
        re.search(
            r"\b(?:cuales?|que|lista|listar|"
            r"listado|detalle|detalla)\b",
            texto,
        )
    )

    # Una consulta exclusivamente de conteo
    # no necesita mostrar los nombres.

    if contar and not listar:
        return bloque

    for fila, saldo in seleccion[:MAX_LISTADO]:

        nombre = fila.get("nombre") or "Cuenta sin nombre"

        bloque.filas.append((
            (),
            (
                f"**{nombre}:** "
                f"{etiqueta} {motor._dinero(saldo)}."
            ),
        ))

    if len(seleccion) > MAX_LISTADO:

        bloque.avisos.append(
            f"Se muestran {MAX_LISTADO} de "
            f"{len(seleccion)} cuentas coincidentes."
        )

    return bloque


def _clasificar_categorias(texto, contexto):

    if not re.search(r"\bcategorias?\b", texto):
        return None

    mayor = bool(
        re.search(
            r"\b(?:mas|mayor(?:es)?|"
            r"principal(?:es)?|top)\b",
            texto,
        )
    )

    menor = bool(
        re.search(
            r"\b(?:menos|menor(?:es)?)\b",
            texto,
        )
    )

    listado = bool(
        re.search(
            r"\b(?:que|cuales?)\s+categorias?\b"
            r"|\bpor\s+categorias?\b"
            r"|\bdesglose\b",
            texto,
        )
    )

    if not mayor and not menor and not listado:
        return None

    titulo = "Ingresos y gastos"

    if mayor and menor:

        return _bloque_limitacion(
            titulo,
            "Indica si quieres consultar las categorías "
            "con mayores o menores gastos.",
        )

    filas = contexto.get(
        "postgresql", {}
    ).get("gastos_por_categoria")

    if not isinstance(filas, list):

        return _bloque_limitacion(
            titulo,
            "No se recuperó evidencia suficiente "
            "para clasificar los gastos por categoría.",
        )

    registros = []

    for fila in filas:

        nombre = fila.get("categoria")

        monto = motor._decimal(
            fila.get("total_incluido_gmf")
        )

        if not isinstance(nombre, str) or monto is None:

            return _bloque_limitacion(
                titulo,
                "No hay datos válidos para completar "
                "la clasificación de categorías.",
            )

        registros.append((nombre, monto))

    if not registros:

        return _bloque_limitacion(
            titulo,
            "No hay gastos ordinarios por categoría "
            "registrados en el período consultado.",
        )

    registros.sort(
        key=lambda fila: (
            fila[1] if menor else -fila[1],
            normalizar(fila[0]),
        )
    )

    limite = (
        MAX_CLASIFICACION
        if mayor or menor
        else MAX_LISTADO
    )

    if mayor:
        descripcion = "Categorías con mayores gastos"

    elif menor:
        descripcion = (
            "Categorías con menores gastos registrados"
        )

    else:
        descripcion = "Gastos por categoría"

    bloque = motor.Bloque(
        titulo=titulo,
        resumen=[
            f"{descripcion}:"
        ],
    )

    for nombre, monto in registros[:limite]:

        bloque.filas.append((
            (),
            f"**{nombre}:** {motor._dinero(monto)}",
        ))

    if len(registros) > limite:

        bloque.avisos.append(
            f"Se muestran {limite} de "
            f"{len(registros)} categorías con gastos registrados."
        )

    bloque.avisos.append(
        "Los importes incluyen el GMF correspondiente "
        "a los gastos ordinarios de cada categoría."
    )

    return bloque


def construir_bloque_colectivo(
    pregunta,
    contexto,
    dominio,
):
    """None indica que no se reconoció una operación colectiva."""

    texto = normalizar(pregunta)

    if dominio == "cuentas":

        return _consultar_cuentas(
            texto,
            contexto,
        )

    if dominio == "movimientos":

        return _clasificar_categorias(
            texto,
            contexto,
        )

    return None
