
"""Recuperacion eficiente del contexto RAG.

Business Layer.

Seleccion de temas y validacion del alcance temporal.
Conserva la recuperacion financiera completa.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.business.movimiento_service import (
    calcular_periodo,
    consultar_resumen_mensual,
)

from app.business.planificacion_service import (
    consultar_planificacion,
    TEMAS_PLANIFICACION,
)

from app.business.rag_intencion import (
    interpretar_pregunta,
    normalizar,
)

from app.business.rag_alcance import (
    resolver_periodo,
    mes_anterior,
    AlcanceNoAdmitido,
)

from app.business.rag_relaciones_276 import (
    resumir_reservas,
)

from app.persistence.cuenta_repository import (
    obtener_cuentas_con_saldo,
)

from app.persistence.movimiento_repository import (
    obtener_movimientos_mes,
)

from app.persistence.rag_financiero_repository import (
    obtener_aportes_vinculados,
)

from app.persistence.rag_semantico_basico_repository import (
    obtener_contexto_semantico_basico,
)

from app.persistence.rag_semantico_repository import (
    EvidenciaSemanticaInvalida,
)

from app.services.fuseki_client import (
    consultar_select,
)


CERO = Decimal("0.00")


def _normalizar(texto: str) -> str:
    return normalizar(texto)


def _periodo(pregunta: str, hoy: date):

    try:

        return resolver_periodo(
            pregunta,
            hoy,
        )

    except AlcanceNoAdmitido as error:

        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error


def _temas_relevantes(
    pregunta: str,
) -> set[str]:

    return set(
        interpretar_pregunta(pregunta).temas
    )


def _datos_sparql(
    id_usuario: int,
    incluir_categorias: bool = True,
) -> dict:

    try:

        return obtener_contexto_semantico_basico(
            id_usuario=id_usuario,
            incluir_categorias=incluir_categorias,
            ejecutar=consultar_select,
        )

    except EvidenciaSemanticaInvalida as error:

        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error


def _construir_cuentas(
    db: Session,
    id_usuario: int,
    reservas_por_par: dict,
) -> list[dict]:

    reservado_por_cuenta = defaultdict(
        lambda: CERO
    )

    for (_, id_cuenta), monto in (
        reservas_por_par.items()
    ):

        reservado_por_cuenta[id_cuenta] += monto

    cuentas = []

    for fila in obtener_cuentas_con_saldo(
        db,
        id_usuario,
    ):

        if fila["estado"] != "ACTIVA":
            continue

        real = Decimal(
            fila["saldo_actual"]
        )

        reservado = reservado_por_cuenta[
            fila["id_cuenta"]
        ]

        libre = real - reservado

        if reservado < CERO or libre < CERO:

            raise HTTPException(
                status_code=409,
                detail="Saldos y reservas inconsistentes",
            )

        cuentas.append({
            "id_cuenta": fila["id_cuenta"],
            "nombre": fila["nombre_cuenta"],
            "tipo": fila["tipo_cuenta"],
            "saldo_real": str(real),
            "reservado": str(reservado),
            "saldo_libre": str(libre),
        })

    return cuentas


def _resumen_cuentas(cuentas: list[dict]) -> dict:

    def total(campo):

        return str(
            sum(
                (
                    Decimal(cuenta[campo])
                    for cuenta in cuentas
                ),
                CERO,
            )
        )

    return {
        "numero_cuentas_activas": len(cuentas),
        "saldo_real_total": total("saldo_real"),
        "reservado_total": total("reservado"),
        "saldo_libre_total": total("saldo_libre"),
    }


def _construir_movimientos(
    db: Session,
    id_usuario: int,
    anio: int,
    mes: int,
) -> dict:

    inicio, fin = calcular_periodo(
        anio,
        mes,
    )

    resumen = consultar_resumen_mensual(
        db,
        id_usuario,
        anio,
        mes,
    )

    movimientos = obtener_movimientos_mes(
        db,
        id_usuario,
        inicio,
        fin,
    )

    gastos = defaultdict(
        lambda: CERO
    )

    for movimiento in movimientos:

        if (
            movimiento["estado"] != "ACTIVO"
            or movimiento["origen"] != "NORMAL"
            or movimiento["tipo"] != "GASTO"
        ):
            continue

        categoria = (
            movimiento["nombre_categoria"]
            or "Sin categoría"
        )

        gastos[categoria] += (
            Decimal(movimiento["monto"])
            + Decimal(movimiento["monto_gmf"])
        )

    ordenados = sorted(
        gastos.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    return {
        "resumen_mensual": {

            "ingresos_ordinarios": str(
                resumen["ingresos_ordinarios"]
            ),

            "gastos_ordinarios": str(
                resumen["gastos_ordinarios"]
            ),

            "gmf_total": str(
                resumen["gmf_total"]
            ),
        },

        "gastos_por_categoria": [
            {
                "categoria": nombre,
                "total_incluido_gmf": str(total),
            }

            for nombre, total in ordenados
        ],
    }


def construir_contexto_rag(
    db: Session,
    id_usuario: int,
    pregunta: str,
    hoy: date | None = None,
) -> dict:

    if type(id_usuario) is not int or id_usuario <= 0:

        raise ValueError("Usuario inválido")

    hoy = hoy or date.today()

    anio, mes = _periodo(
        pregunta,
        hoy,
    )

    temas = _temas_relevantes(
        pregunta
    )

    periodo_actual = (
        anio,
        mes,
    ) == (
        hoy.year,
        hoy.month,
    )

    # Movimientos y presupuestos se pueden
    # recuperar por mes.
    #
    # Cuentas, metas, reservas y obligaciones
    # representan el estado actual y no deben
    # presentarse como instantaneas historicas.

    if (
        not periodo_actual

        and temas.intersection({
            "cuentas",
            "metas",
            "obligaciones",
        })
    ):

        raise HTTPException(
            status_code=422,

            detail=(
                "El período histórico solo se admite "
                "para movimientos y presupuestos. "
                "Consulta las cuentas, metas y "
                "obligaciones actuales por separado."
            ),
        )

    if periodo_actual:

        interpretacion = "Mes actual"

    elif (
        anio,
        mes,
    ) == mes_anterior(hoy):

        interpretacion = "Mes pasado"

    else:

        interpretacion = "Mes histórico solicitado"

    evidencia_sql = {}
    analisis = {}

    # PLANIFICACION SELECTIVA

    temas_plan = temas.intersection(
        TEMAS_PLANIFICACION
    )

    plan = {}

    if temas_plan:

        plan = consultar_planificacion(
            db,
            id_usuario,
            temas=temas_plan,
        )

    # RESERVAS COMPARTIDAS

    if temas.intersection({
        "cuentas",
        "metas",
    }):

        filas = obtener_aportes_vinculados(
            db,
            id_usuario,
        )

        resumen_reservas, pares = (
            resumir_reservas(filas)
        )

        if "metas" in temas:

            analisis["reservas"] = (
                resumen_reservas
            )

        if "cuentas" in temas:

            cuentas = _construir_cuentas(
                db,
                id_usuario,
                pares,
            )

            evidencia_sql["cuentas"] = (
                cuentas
            )

            analisis["cuentas"] = (
                _resumen_cuentas(cuentas)
            )

    # MOVIMIENTOS

    if "movimientos" in temas:

        evidencia_sql.update(
            _construir_movimientos(
                db,
                id_usuario,
                anio,
                mes,
            )
        )

    # PRESUPUESTOS

    if "presupuestos" in temas:

        evidencia_sql["presupuestos"] = [
            {
                "categoria": p["categoria"],
                "limite": str(p["monto_limite"]),
                "gastado": str(p["gastado"]),
                "disponible": str(p["disponible"]),
                "porcentaje_usado": str(
                    p["porcentaje_usado"]
                ),
            }

            for p in plan["presupuestos"]

            if p["anio"] == anio
            and p["mes"] == mes
        ]

    # METAS

    if "metas" in temas:

        evidencia_sql["metas"] = [
            {
                "id_meta": m["id_meta"],
                "nombre": m["nombre_meta"],
                "objetivo": str(m["monto_objetivo"]),
                "acumulado": str(m["monto_acumulado"]),
                "progreso_porcentaje": str(
                    m["porcentaje_progreso"]
                ),
                "estado": m["estado"],
            }

            for m in plan["metas"]
        ]

    # OBLIGACIONES

    if "obligaciones" in temas:

        evidencia_sql["obligaciones"] = [
            {
                "id_obligacion": o["id_obligacion"],
                "nombre": o["nombre_obligacion"],
                "tipo": o["tipo_obligacion"],
                "pendiente": str(o["monto_pendiente"]),
                "estado": o["estado"],
            }

            for o in plan["obligaciones"]
        ]

    # RECUPERACION SEMANTICA SELECTIVA

    semantica = _datos_sparql(
        id_usuario,

        incluir_categorias=bool(
            temas.intersection({
                "movimientos",
                "presupuestos",
            })
        ),
    )

    return {
        "pregunta": pregunta,

        "periodo": {
            "anio": anio,
            "mes": mes,
            "interpretacion": interpretacion,
        },

        "moneda": "COP",

        "temas_recuperados": sorted(
            temas
        ),

        "postgresql": evidencia_sql,

        "analisis_financiero": analisis,

        "fuseki": semantica,

        "fuentes": [
            {
                "origen": "PostgreSQL",
                "tipo": "datos financieros recuperados",
            },
            {
                "origen": "Fuseki/SPARQL",
                "tipo": "grafo semántico del usuario",
                "fecha": semantica["fecha_instantanea"],
            },
        ],

        "limitaciones": [
            "Los importes financieros provienen de PostgreSQL.",
            "Fuseki contiene una instantánea que puede estar desactualizada.",
            "El análisis no incluye operaciones offline sin sincronizar.",
            "Se admite el mes actual, anterior o un mes y año explícitos.",
            "Los períodos históricos se limitan a movimientos y presupuestos.",
            "Los saldos, metas y obligaciones representan su estado actual.",
            "Los gastos por categoría incluyen GMF cuando existe.",
            "Las categorías RDF describen el grafo publicado, no una instantánea histórica del mes solicitado.",
            "No se exportan descripciones de movimientos ni credenciales.",
        ],
    }
