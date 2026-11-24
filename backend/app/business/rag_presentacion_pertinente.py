
"""Presentacion pertinente del asistente financiero.

Business Layer.

Filtra entidades y operaciones colectivas antes
de limitar detalles. No consulta bases de datos.
"""

from collections import Counter
from decimal import Decimal

from app.business import rag_motor_respuestas as motor

from app.business.rag_contexto_ia import _preparar

from app.business.rag_intencion import interpretar_pregunta

from app.business.rag_alcance import (
    referencia_entidad,
    resolver_entidad,
    AlcanceNoAdmitido,
)

from app.business.rag_operaciones_colectivas import (
    construir_bloque_colectivo,
)

from app.business.rag_relaciones_276 import (
    resumir_obligaciones,
)


ETIQUETAS_CUENTAS = {
    "numero_cuentas_activas": "Cuentas activas",
    "saldo_real_total": "Saldo real total",
    "reservado_total": "Dinero reservado",
    "saldo_libre_total": "Saldo libre disponible",
}

CAMPOS_FILA_CUENTA = {
    "saldo_real_total": ("saldo_real", "saldo real"),
    "reservado_total": ("reservado", "reservado"),
    "saldo_libre_total": ("saldo_libre", "disponible"),
}

ETIQUETAS_MOVIMIENTOS = {
    "ingresos_ordinarios": "Ingresos ordinarios",
    "gastos_ordinarios": "Gastos ordinarios",
    "gmf_total": "GMF registrado",
}

TITULOS = {
    "cuentas": "Cuentas y liquidez",
    "movimientos": "Ingresos y gastos",
    "obligaciones": "Deudas y dinero por cobrar",
    "presupuestos": "Presupuestos",
    "metas": "Metas financieras",
    "reservas": "Reservas y distribución por metas",
}


def _coincide(fila, regla):

    return (
        fila.get(
            "tipo",
            fila.get("tipo_obligacion"),
        ) == regla.tipo
        and fila.get("estado") in regla.estados
    )


def _sin_avisos_detalle(bloque):

    bloque.avisos = [
        aviso
        for aviso in bloque.avisos
        if not aviso.startswith("Detalle de ")
    ]


def _bloque_entidad(
    pregunta,
    contexto,
    intencion,
    dominio,
):

    referencia = referencia_entidad(
        pregunta,
        dominio,
    )

    if referencia is None or referencia in {
        "total",
        "general",
        "conjunto",
    }:
        return None

    sql = contexto.get("postgresql", {})

    bloque = motor.Bloque(TITULOS[dominio])

    try:

        if dominio == "cuentas":

            filas = sql.get("cuentas")

            if not isinstance(filas, list):

                raise AlcanceNoAdmitido(
                    "No se recuperó evidencia suficiente "
                    "para identificar la cuenta."
                )

            cuenta = resolver_entidad(
                referencia,
                filas,
                "nombre",
                "cuenta",
            )

            nombre = cuenta["nombre"]

            for campo in intencion.campos_cuentas:

                if campo == "numero_cuentas_activas":

                    bloque.resumen.append(
                        f"Cuenta activa identificada: {nombre}."
                    )

                    continue

                configuracion = CAMPOS_FILA_CUENTA.get(
                    campo
                )

                if configuracion is None:
                    continue

                campo_fila, _ = configuracion

                etiqueta = ETIQUETAS_CUENTAS[campo]

                bloque.resumen.append(
                    f"{etiqueta} en {nombre}: "
                    f"{motor._dinero(cuenta.get(campo_fila))}"
                )

        elif dominio == "movimientos":

            if (
                "gastos_ordinarios"
                not in intencion.campos_movimientos
                or "ingresos_ordinarios"
                in intencion.campos_movimientos
            ):

                raise AlcanceNoAdmitido(
                    "No puedo filtrar los ingresos por "
                    "esa entidad con la evidencia disponible."
                )

            filas = sql.get("gastos_por_categoria")

            if not isinstance(filas, list):

                raise AlcanceNoAdmitido(
                    "No se recuperó evidencia suficiente "
                    "para identificar la categoría."
                )

            categoria = resolver_entidad(
                referencia,
                filas,
                "categoria",
                "categoría",
            )

            bloque.resumen.append(
                f"Gastos en {categoria['categoria']}: "
                f"{motor._dinero(categoria.get('total_incluido_gmf'))}"
            )

            bloque.avisos.append(
                "El importe incluye GMF cuando "
                "corresponde a los gastos de esta categoría."
            )

    except AlcanceNoAdmitido as error:

        bloque.resumen = [str(error)]
        bloque.filas = []
        bloque.avisos = []

    return bloque


def _seleccionar_contexto(contexto, intencion):

    sql_original = contexto.get("postgresql", {})
    analisis_original = contexto.get(
        "analisis_financiero", {}
    )

    secciones = set(intencion.secciones)

    sql = {}
    analisis = {}

    if "cuentas" in secciones:

        if "cuentas" in sql_original:

            filas = sql_original["cuentas"]

            if not intencion.listar_cuentas:

                filas = []

            elif intencion.solo_cuentas_reservadas:

                filas = [
                    fila
                    for fila in filas
                    if (
                        motor._decimal(fila.get("reservado"))
                        or Decimal("0")
                    ) > 0
                ]

            sql["cuentas"] = filas

        if "cuentas" in analisis_original:

            analisis["cuentas"] = analisis_original[
                "cuentas"
            ]

    if "movimientos" in secciones:

        if "resumen_mensual" in sql_original:

            resumen = sql_original["resumen_mensual"]

            sql["resumen_mensual"] = {
                campo: resumen[campo]
                for campo in intencion.campos_movimientos
                if campo in resumen
            }

        if (
            intencion.listar_categorias
            and "gastos_por_categoria" in sql_original
        ):

            sql["gastos_por_categoria"] = sql_original[
                "gastos_por_categoria"
            ]

    if "obligaciones" in secciones:

        if "obligaciones" in sql_original:

            sql["obligaciones"] = [
                fila
                for fila in sql_original["obligaciones"]
                if any(
                    regla.listar
                    and _coincide(fila, regla)
                    for regla in intencion.reglas_obligaciones
                )
            ]

        if "obligaciones" in analisis_original:

            analisis["obligaciones"] = analisis_original[
                "obligaciones"
            ]

    if "presupuestos" in secciones:

        if "presupuestos" in sql_original:

            sql["presupuestos"] = sql_original[
                "presupuestos"
            ]

    if "metas" in secciones:

        if "metas" in sql_original:

            sql["metas"] = [
                fila
                for fila in sql_original["metas"]
                if (
                    intencion.estado_meta is None
                    or fila.get("estado")
                    == intencion.estado_meta
                )
            ]

    if "reservas" in secciones:

        if "reservas" in analisis_original:

            analisis["reservas"] = analisis_original[
                "reservas"
            ]

    return {
        **contexto,
        "postgresql": sql,
        "analisis_financiero": analisis,
    }


def _ajustar_cuentas(
    bloque,
    evidencia,
    registro,
    intencion,
):

    datos = evidencia.get(
        "analisis_financiero", {}
    ).get("cuentas", {})

    resumen = []

    for campo in intencion.campos_cuentas:

        etiqueta = ETIQUETAS_CUENTAS[campo]

        valor = datos.get(campo)

        if campo == "numero_cuentas_activas":

            valor = motor._conteo(valor)

        else:

            valor = motor._dinero(valor)

        resumen.append(f"{etiqueta}: {valor}")

    bloque.resumen = resumen

    if not intencion.listar_cuentas:

        bloque.filas = []
        _sin_avisos_detalle(bloque)

        return

    duplicados = Counter(registro.nombres.values())

    filas = []

    for fila in evidencia.get(
        "postgresql", {}
    ).get("cuentas", []):

        alias = fila.get("nombre")

        nombre = motor._nombre(
            alias,
            registro,
            duplicados,
        )

        detalles = []

        for campo in intencion.campos_cuentas:

            configuracion = CAMPOS_FILA_CUENTA.get(campo)

            if configuracion is None:
                continue

            clave, etiqueta = configuracion

            detalles.append(
                f"{etiqueta} "
                f"{motor._dinero(fila.get(clave))}"
            )

        if detalles:

            filas.append((
                (alias,),
                f"**{nombre}:** "
                + "; ".join(detalles)
                + ".",
            ))

    bloque.filas = filas

    if not filas:

        bloque.avisos.append(
            "No hay cuentas que coincidan "
            "con el filtro solicitado."
        )


def _ajustar_movimientos(
    bloque,
    evidencia,
    intencion,
):

    resumen = evidencia.get(
        "postgresql", {}
    ).get("resumen_mensual", {})

    bloque.resumen = [
        (
            ETIQUETAS_MOVIMIENTOS[campo]
            + ": "
            + motor._dinero(resumen.get(campo))
        )
        for campo in intencion.campos_movimientos
    ]

    if not intencion.listar_categorias:

        bloque.filas = []
        _sin_avisos_detalle(bloque)


def _etiqueta_obligaciones(regla):

    base = (
        "Deudas propias"
        if regla.tipo == "POR_PAGAR"
        else "Cobros"
    )

    if regla.estados == ("ACTIVA",):

        return (
            base + " activos"
            if regla.tipo == "POR_COBRAR"
            else base + " activas"
        )

    if regla.estados == ("SALDADA",):

        return (
            base + " saldados"
            if regla.tipo == "POR_COBRAR"
            else base + " saldadas"
        )

    if regla.estados == ("INACTIVA",):

        return (
            base + " inactivos"
            if regla.tipo == "POR_COBRAR"
            else base + " inactivas"
        )

    return (
        base
        + " ("
        + ", ".join(regla.estados)
        + ")"
    )


def _etiqueta_importe(regla):

    if regla.estados == ("ACTIVA",):

        if regla.tipo == "POR_PAGAR":
            return "Total pendiente por pagar"

        return "Total pendiente por cobrar"

    return (
        "Saldo pendiente de "
        + _etiqueta_obligaciones(regla).lower()
    )


def _ajustar_obligaciones(
    bloque,
    contexto,
    intencion,
):

    obligaciones = contexto.get(
        "postgresql", {}
    ).get("obligaciones")

    resumen = contexto.get(
        "analisis_financiero", {}
    ).get("obligaciones", {})

    bloque.resumen = []

    if (
        not isinstance(obligaciones, list)
        or type(
            resumen.get("obligaciones_totales")
        ) is not int
        or resumen["obligaciones_totales"]
        != len(obligaciones)
    ):

        bloque.filas = []

        bloque.avisos.append(
            "No se dispone de una lista completa "
            "de obligaciones para aplicar "
            "los filtros solicitados."
        )

        return

    resumir_obligaciones(obligaciones)

    for regla in intencion.reglas_obligaciones:

        seleccion = [
            fila
            for fila in obligaciones
            if _coincide(fila, regla)
        ]

        if regla.contar:

            bloque.resumen.append(
                _etiqueta_obligaciones(regla)
                + ": "
                + str(len(seleccion))
            )

        if regla.sumar:

            total = sum(
                (
                    Decimal(
                        str(
                            fila.get(
                                "pendiente",
                                fila.get("monto_pendiente"),
                            )
                        )
                    )
                    for fila in seleccion
                ),
                Decimal("0.00"),
            )

            bloque.resumen.append(
                _etiqueta_importe(regla)
                + ": "
                + motor._dinero(total)
            )

    if not any(
        regla.listar
        for regla in intencion.reglas_obligaciones
    ):

        bloque.filas = []
        _sin_avisos_detalle(bloque)


def _ajustar_reservas(
    bloque,
    evidencia,
    intencion,
):

    datos = evidencia.get(
        "analisis_financiero", {}
    ).get("reservas", {})

    bloque.resumen = [
        "Total reservado vinculado: "
        + motor._dinero(
            datos.get("total_reservado_vinculado")
        )
    ]

    if not intencion.listar_reservas:

        bloque.filas = []
        _sin_avisos_detalle(bloque)


def _evidencia_minima(contexto):

    return {
        "periodo": contexto.get("periodo", {}),

        "fuseki": {
            "vigencia": contexto.get(
                "fuseki", {}
            ).get("vigencia"),
        },
    }


def _preparar_respuesta(
    pregunta,
    contexto,
    incluir_rdf,
):

    intencion = interpretar_pregunta(pregunta)

    contexto = motor._contexto_completo(contexto)

    # OPERACIONES COLECTIVAS Y ENTIDADES.
    #
    # Se evalúan antes de limitar los registros.
    # Una condición numérica nunca debe tratarse
    # como el nombre de una entidad.

    if len(intencion.secciones) == 1:

        dominio = intencion.secciones[0]

        if dominio in {"cuentas", "movimientos"}:

            colectivo = construir_bloque_colectivo(
                pregunta,
                contexto,
                dominio,
            )

            if colectivo is not None:

                return (
                    intencion,
                    "",
                    _evidencia_minima(contexto),
                    {dominio: colectivo},
                )

            especifico = _bloque_entidad(
                pregunta,
                contexto,
                intencion,
                dominio,
            )

            if especifico is not None:

                return (
                    intencion,
                    "",
                    _evidencia_minima(contexto),
                    {dominio: especifico},
                )

    # FLUJO GENERAL PREVIAMENTE APROBADO.

    seleccionado = _seleccionar_contexto(
        contexto,
        intencion,
    )

    pregunta_limpia, evidencia, registro = _preparar(
        pregunta,
        seleccionado,
    )

    disponibles = motor.construir_bloques(
        evidencia,
        registro,
        incluir_rdf=incluir_rdf,
    )

    bloques = {}

    for clave in intencion.secciones:

        bloque = disponibles.get(clave)

        if bloque is None:

            bloque = motor.Bloque(
                titulo=TITULOS[clave],
                resumen=[
                    "No se recuperó evidencia "
                    "suficiente para esta sección."
                ],
            )

        elif clave == "cuentas":

            _ajustar_cuentas(
                bloque,
                evidencia,
                registro,
                intencion,
            )

        elif clave == "movimientos":

            _ajustar_movimientos(
                bloque,
                evidencia,
                intencion,
            )

        elif clave == "obligaciones":

            _ajustar_obligaciones(
                bloque,
                contexto,
                intencion,
            )

        elif clave == "reservas":

            _ajustar_reservas(
                bloque,
                evidencia,
                intencion,
            )

        bloques[clave] = bloque

    return (
        intencion,
        pregunta_limpia,
        evidencia,
        bloques,
    )


def _renderizar(
    intencion,
    evidencia,
    bloques,
    plan,
    modo_local=False,
    motivo=None,
):

    if intencion.aviso:

        return intencion.aviso

    if not bloques:

        return (
            "No se recuperó evidencia suficiente "
            "para contestar esta consulta."
        )

    lineas = []

    if modo_local:

        lineas.extend([
            "**Resumen financiero local**",
            "",
            motivo
            or "Gemini no está disponible temporalmente.",
            "",
        ])

    if (
        "movimientos" in bloques
        or "presupuestos" in bloques
    ):

        periodo = evidencia.get("periodo", {})

        anio = periodo.get("anio")
        mes = periodo.get("mes")

        if (
            type(anio) is int
            and type(mes) is int
            and 1 <= mes <= 12
        ):

            lineas.extend([
                f"Período: {mes:02d}/{anio}.",
                "",
            ])

    foco = set(plan["foco"])

    multiple = len(bloques) > 1

    for numero, clave in enumerate(
        plan["orden"],
        start=1,
    ):

        bloque = bloques[clave]

        if multiple:

            lineas.extend([
                f"**{numero}. {bloque.titulo}**",
                "",
            ])

        for dato in bloque.resumen:

            if (
                not multiple
                and len(bloque.resumen) == 1
                and not bloque.filas
            ):

                lineas.append(f"**{dato}**")

            else:

                lineas.append(f"- {dato}")

        filas = sorted(
            bloque.filas,
            key=lambda fila: (
                0 if foco.intersection(fila[0])
                else 1
            ),
        )

        for _, texto in filas:

            lineas.append(f"- {texto}")

        if not bloque.resumen and not filas:

            lineas.append(
                "No hay registros que coincidan "
                "con la consulta."
            )

        for aviso in bloque.avisos:

            if (
                not multiple
                and aviso.startswith((
                    "Los conteos agrupados",
                    "Las reservas netas agrupadas",
                ))
            ):
                continue

            lineas.append(f"\nNota: {aviso}")

        lineas.append("")

    if modo_local:

        lineas.append(
            "Fuente: PostgreSQL. "
            "Respuesta construida localmente, "
            "no generada por Gemini."
        )

    elif evidencia.get(
        "fuseki", {}
    ).get("vigencia") == "ANTIGUA":

        lineas.append(
            "Nota: la instantánea RDF tiene "
            "más de 24 horas. Los importes "
            "financieros proceden de PostgreSQL."
        )

    return "\n".join(lineas).strip()


def generar_respuesta_pertinente(
    pregunta: str,
    contexto: dict,
) -> str:

    (
        intencion,
        _pregunta_limpia,
        evidencia,
        bloques,
    ) = _preparar_respuesta(
        pregunta,
        contexto,
        incluir_rdf=True,
    )

    if not bloques:

        raise motor.PlanRespuestaInvalido(
            "No hay secciones financieras utilizables."
        )

    evidencia_plan = {
        "secciones_permitidas": list(bloques),

        "alias_permitidos": sorted(
            motor._alias_disponibles(bloques)
        ),

        "nivel_detalle": (
            "general"
            if intencion.general
            else "puntual"
        ),
    }

    texto = motor.gateway.generar_respuesta_gemini(
        (
            "Organiza las secciones permitidas "
            "sin agregar otras. Conserva el orden "
            "de prioridad recibido salvo que exista "
            "una razón estructural para cambiarlo."
        ),
        evidencia_plan,
        motor.INSTRUCCIONES_PLAN,
    )

    plan = motor.validar_plan(
        texto,
        bloques,
    )

    return _renderizar(
        intencion,
        evidencia,
        bloques,
        plan,
    )


def generar_respuesta_local_pertinente(
    pregunta: str,
    contexto: dict,
    motivo: str | None = None,
) -> str:

    (
        intencion,
        _,
        evidencia,
        bloques,
    ) = _preparar_respuesta(
        pregunta,
        contexto,
        incluir_rdf=False,
    )

    plan = {
        "orden": list(bloques),
        "foco": [],
    }

    return _renderizar(
        intencion,
        evidencia,
        bloques,
        plan,
        modo_local=True,
        motivo=motivo,
    )
