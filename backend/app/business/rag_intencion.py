
"""Interpretacion local de consultas financieras.

Paso 27.7.1 — Business Layer.

Distingue temas de recuperacion, secciones visibles,
estados de obligaciones y nivel de detalle.
"""

import re
import unicodedata

from dataclasses import dataclass


DOMINIOS = (
    "cuentas",
    "movimientos",
    "obligaciones",
    "presupuestos",
    "metas",
)

ESTADOS_OBLIGACION = (
    "ACTIVA",
    "SALDADA",
    "INACTIVA",
)


@dataclass(frozen=True)
class ReglaObligacion:
    tipo: str
    estados: tuple[str, ...]
    contar: bool
    sumar: bool
    listar: bool


@dataclass(frozen=True)
class IntencionFinanciera:
    temas: frozenset[str]
    secciones: tuple[str, ...]
    reglas_obligaciones: tuple[ReglaObligacion, ...]

    campos_cuentas: tuple[str, ...]
    listar_cuentas: bool
    solo_cuentas_reservadas: bool

    campos_movimientos: tuple[str, ...]
    listar_categorias: bool

    estado_meta: str | None
    listar_reservas: bool

    general: bool
    aviso: str | None = None


def normalizar(texto: str) -> str:

    texto = unicodedata.normalize(
        "NFD",
        texto.casefold(),
    )

    return "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )


def _hay(texto, patron):
    return re.search(patron, texto) is not None


def _solicita_listado(texto):

    return _hay(
        texto,
        r"\b(cuales?|quienes?|que|lista(?:me)?|"
        r"listar|listado|detalle|detalla|"
        r"desglosa|distribuid[oa]s?|"
        r"cada|en que|en cuales|"
        r"por categoria)\b",
    )


def _direccion_obligacion(texto):

    cobrar = _hay(
        texto,
        r"\b(por cobrar|me deben|me adeudan|"
        r"pendient\w* de recibir|"
        r"pendient\w* de cobrar|"
        r"dinero a recibir|"
        r"cobros?|deudores?)\b",
    )

    pagar = _hay(
        texto,
        r"\b(por pagar|debo pagar|"
        r"pendient\w* de pagar|"
        r"tengo que pagar|"
        r"deudas? propias)\b",
    )

    deudas = _hay(
        texto,
        r"\b(deudas?|prestamos?)\b",
    )

    obligaciones = _hay(
        texto,
        r"\bobligacion(?:es)?\b",
    )

    if cobrar and pagar:
        return ("POR_PAGAR", "POR_COBRAR")

    if cobrar:
        return ("POR_COBRAR",)

    if pagar or deudas:
        return ("POR_PAGAR",)

    if obligaciones:
        return ("POR_PAGAR", "POR_COBRAR")

    return ()


def _estados(texto, predeterminado):

    activos = _hay(
        texto,
        r"\b(pendient\w*|activ[oa]s?|"
        r"por pagar|por cobrar|"
        r"me deben|me adeudan)\b",
    )

    saldados = _hay(
        texto,
        r"\b(saldad[oa]s?|"
        r"pagad[oa]s?|cobrad[oa]s?|"
        r"liquidad[oa]s?)\b",
    )

    inactivos = _hay(
        texto,
        r"\binactiv[oa]s?\b",
    )

    if _hay(texto, r"\b(todas?|todos)\b"):
        return ESTADOS_OBLIGACION

    resultado = []

    if activos:
        resultado.append("ACTIVA")

    if saldados:
        resultado.append("SALDADA")

    if inactivos:
        resultado.append("INACTIVA")

    return tuple(resultado) or predeterminado


def _operaciones(texto):

    contar = _hay(
        texto,
        r"\b(cuant[oa]s|numero|cantidad)\b",
    )

    sumar = _hay(
        texto,
        r"\b(cuanto|cuanta|total|importe|"
        r"monto|dinero|saldo)\b",
    )

    listar = _solicita_listado(texto)

    # Los listados incluyen sus totales.
    if listar:
        contar = True
        sumar = True

    if not contar and not sumar and not listar:
        contar = True
        sumar = True

    return contar, sumar, listar


def _reglas_obligaciones(texto, general):

    reglas = {}

    partes = [
        p.strip()
        for p in re.split(
            r"[,;?]+|\s+(?:y|e)\s+",
            texto,
        )
        if p.strip()
    ]

    anteriores = ()

    for parte in partes:

        tipos = _direccion_obligacion(parte)

        if not tipos:

            # Permite expresiones coordinadas:
            # "deudas pendientes y saldadas".
            if anteriores and _hay(
                parte,
                r"^(?:saldad|activ|inactiv|pendient)",
            ):
                tipos = anteriores
            else:
                continue

        anteriores = tipos

        estados = _estados(
            parte,
            ("ACTIVA",),
        )

        contar, sumar, listar = _operaciones(
            parte,
        )

        if general and not listar:
            contar = True
            sumar = True

        for tipo in tipos:

            clave = (tipo, estados)

            previa = reglas.get(clave)

            reglas[clave] = ReglaObligacion(
                tipo=tipo,
                estados=estados,
                contar=contar or bool(
                    previa and previa.contar
                ),
                sumar=sumar or bool(
                    previa and previa.sumar
                ),
                listar=listar or bool(
                    previa and previa.listar
                ),
            )

    if general and not reglas:

        for tipo in (
            "POR_PAGAR",
            "POR_COBRAR",
        ):
            reglas[(tipo, ("ACTIVA",))] = (
                ReglaObligacion(
                    tipo,
                    ("ACTIVA",),
                    True,
                    True,
                    False,
                )
            )

    return tuple(reglas.values())


def interpretar_pregunta(
    pregunta: str,
) -> IntencionFinanciera:

    texto = normalizar(pregunta)

    general = _hay(
        texto,
        r"\b(situacion financiera|"
        r"panorama financiero|"
        r"resumen financiero|"
        r"mis finanzas|"
        r"todas mis finanzas|"
        r"analisis financiero|"
        r"estado de mis finanzas)\b",
    )

    reglas = _reglas_obligaciones(
        texto,
        general,
    )

    # Evita confundir cuentas por cobrar
    # con cuentas bancarias.
    texto_cuentas = re.sub(
        r"\bcuentas?\s+por\s+(?:pagar|cobrar)\b",
        "",
        texto,
    )

    reserva = _hay(
        texto,
        r"\b(reserv\w*|liberacion(?:es)?)\b",
    )

    metas = _hay(
        texto,
        r"\b(metas?|objetivos?|ahorros?)\b",
    )

    presupuestos = _hay(
        texto,
        r"\b(presupuestos?|limite(?:s)?)\b",
    )

    ingresos = _hay(
        texto,
        r"\b(ingresos?|ganancias?)\b",
    )

    gastos = _hay(
        texto,
        r"\b(gastos?|gaste|gastado|gastando|"
        r"gmf|4x1000|4 por mil|"
        r"consumos?|categorias?|"
        r"restaurantes?)\b",
    )

    cuentas_explicitas = _hay(
        texto_cuentas,
        r"\b(cuentas?|liquidez|efectivo)\b",
    )

    saldo_libre = _hay(
        texto,
        r"\b(saldo libre|saldo disponible|"
        r"dinero disponible|disponible|"
        r"puedo gastar|utilizar libremente|"
        r"usar libremente)\b",
    )

    saldo_real = _hay(
        texto,
        r"\b(saldo real|saldo total|"
        r"saldo actual)\b",
    )

    # "Disponible del presupuesto" no es
    # disponibilidad bancaria.
    if presupuestos and not cuentas_explicitas:
        saldo_libre = False

    dinero_generico = (
        not reglas
        and not metas
        and not reserva
        and not presupuestos
        and not ingresos
        and not gastos
        and _hay(
            texto,
            r"\b(dinero tengo|"
            r"tengo dinero|saldo|"
            r"cuanto tengo)\b",
        )
    )

    cuentas = (
        cuentas_explicitas
        or saldo_libre
        or saldo_real
        or dinero_generico
    )

    # Una consulta exclusivamente relacional
    # no necesita mostrar toda la liquidez.
    relacion_reservas = (
        reserva and (
            metas
            or _hay(
                texto,
                r"\b(distribuid\w*|"
                r"distribucion|relacion\w*|"
                r"entre las cuentas)\b",
            )
        )
    )

    temas = set()
    secciones = []

    if cuentas:
        temas.add("cuentas")

        if (
            not relacion_reservas
            or saldo_libre
            or saldo_real
            or general
        ):
            secciones.append("cuentas")

    if ingresos or gastos:
        temas.add("movimientos")
        secciones.append("movimientos")

    if reglas and (
        not general
        or _direccion_obligacion(texto)
    ):
        temas.add("obligaciones")
        secciones.append("obligaciones")

    if presupuestos:
        temas.add("presupuestos")
        secciones.append("presupuestos")

    if metas:
        temas.add("metas")

        # Si se solicitan exclusivamente reservas
        # por meta, no mostrar todas las metas.
        if not relacion_reservas or general:
            secciones.append("metas")

    if reserva:

        # Dependencias financieras internas.
        temas.update({"cuentas", "metas"})

        if relacion_reservas:
            secciones.append("reservas")

        elif "cuentas" not in secciones:
            secciones.append("cuentas")

    if general:

        if not temas:
            temas.update(DOMINIOS)

            secciones = [
                *DOMINIOS,
                "reservas",
            ]

        elif (
            "cuentas" in temas
            and "metas" in temas
            and "reservas" not in secciones
        ):
            secciones.append("reservas")

        # Un analisis general de obligaciones
        # incluye ambos sentidos financieros.
        if (
            "obligaciones" in secciones
            and not _hay(
                texto,
                r"\b(por pagar|por cobrar|"
                r"pendient\w*|saldad\w*)\b",
            )
        ):
            reglas = tuple(
                ReglaObligacion(
                    tipo,
                    ("ACTIVA",),
                    True,
                    True,
                    False,
                )
                for tipo in (
                    "POR_PAGAR",
                    "POR_COBRAR",
                )
            )

    campos_cuentas = []

    if general:
        campos_cuentas = [
            "numero_cuentas_activas",
            "saldo_real_total",
            "reservado_total",
            "saldo_libre_total",
        ]

    else:

        if saldo_real:
            campos_cuentas.append(
                "saldo_real_total"
            )

        if reserva and "reservas" not in secciones:
            campos_cuentas.append(
                "reservado_total"
            )

        if saldo_libre:
            campos_cuentas.append(
                "saldo_libre_total"
            )

        if _hay(
            texto,
            r"\bcuantas cuentas\b",
        ):
            campos_cuentas.append(
                "numero_cuentas_activas"
            )

        if not campos_cuentas:
            campos_cuentas.append(
                "saldo_libre_total"
            )

    listar_cuentas = (
        not general
        and _solicita_listado(texto)
        and cuentas_explicitas
    )

    campos_movimientos = []

    if general or ingresos:
        campos_movimientos.append(
            "ingresos_ordinarios"
        )

    if general or gastos:
        campos_movimientos.extend([
            "gastos_ordinarios",
            "gmf_total",
        ])

    estado_meta = None

    if _hay(
        texto,
        r"\bmetas?\s+activas?\b",
    ):
        estado_meta = "ACTIVA"

    elif _hay(
        texto,
        r"\bmetas?\s+cumplidas?\b",
    ):
        estado_meta = "CUMPLIDA"

    aviso = None

    if not temas:

        aviso = (
            "No se identifico una consulta "
            "financiera suficientemente concreta. "
            "Indica si necesitas consultar cuentas, "
            "ingresos, gastos, presupuestos, "
            "obligaciones o metas."
        )

    return IntencionFinanciera(
        temas=frozenset(temas),

        secciones=tuple(
            dict.fromkeys(secciones)
        ),

        reglas_obligaciones=reglas,

        campos_cuentas=tuple(campos_cuentas),

        listar_cuentas=listar_cuentas,

        solo_cuentas_reservadas=(
            reserva
            and not saldo_libre
            and not saldo_real
            and not general
        ),

        campos_movimientos=tuple(
            campos_movimientos
        ),

        listar_categorias=(
            general
            or _hay(
                texto,
                r"\b(categorias?|"
                r"en que gasto|"
                r"en que gaste|"
                r"desglose)\b",
            )
        ),

        estado_meta=estado_meta,

        listar_reservas=(
            relacion_reservas
            and (
                _solicita_listado(texto)
                or _hay(
                    texto,
                    r"\b(como|distribucion|"
                    r"distribuid\w*)\b",
                )
            )
        ),

        general=general,

        aviso=aviso,
    )
