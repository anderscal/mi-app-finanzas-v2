
"""Análisis financiero y verificación SQL/RDF.

Capa Business.

Reutiliza la evidencia recuperada dentro de la
misma solicitud y delega el acceso a Persistence.
"""

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.business.planificacion_service import (
    consultar_planificacion,
)

from app.persistence.rag_financiero_repository import (
    obtener_aportes_vinculados,
)

from app.persistence import (
    rag_semantico_repository as semrepo,
)

from app.services.fuseki_client import (
    consultar_select,
)


FIN = semrepo.FIN
OP = semrepo.OP

CERO = Decimal("0.00")

TIPOS = {
    "POR_PAGAR",
    "POR_COBRAR",
}

ESTADOS = {
    "ACTIVA",
    "SALDADA",
    "INACTIVA",
}


def _decimal(valor) -> Decimal:
    try:
        numero = Decimal(str(valor))
    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ) as error:
        raise HTTPException(
            409,
            "Importe financiero no válido",
        ) from error

    if not numero.is_finite() or numero < CERO:
        raise HTTPException(
            409,
            "Importe financiero inconsistente",
        )

    return numero


def resumir_obligaciones(
    obligaciones: list[dict],
) -> tuple[dict, dict]:

    conteos = defaultdict(int)

    por_cobrar = CERO
    por_pagar = CERO

    for o in obligaciones:

        # Admite el contrato original de planificación
        # y el contrato normalizado del contexto RAG.
        tipo = o.get(
            "tipo_obligacion",
            o.get("tipo"),
        )

        estado = o["estado"]

        if tipo not in TIPOS or estado not in ESTADOS:
            raise HTTPException(
                409,
                "Tipo o estado de obligación inválido",
            )

        pendiente = _decimal(
            o.get(
                "monto_pendiente",
                o.get("pendiente"),
            )
        )

        if estado == "SALDADA" and pendiente != CERO:
            raise HTTPException(
                409,
                "Obligación saldada con saldo pendiente",
            )

        conteos[(tipo, estado)] += 1

        if estado == "ACTIVA":

            if tipo == "POR_COBRAR":
                por_cobrar += pendiente

            elif tipo == "POR_PAGAR":
                por_pagar += pendiente

    conteos_presentes = {
        clave: cantidad
        for clave, cantidad in conteos.items()
        if cantidad > 0
    }

    return {
        "obligaciones_totales": len(obligaciones),

        "deudas_propias_saldadas": conteos[
            ("POR_PAGAR", "SALDADA")
        ],

        "cobros_saldados": conteos[
            ("POR_COBRAR", "SALDADA")
        ],

        "deudas_propias_activas": conteos[
            ("POR_PAGAR", "ACTIVA")
        ],

        "cobros_activos": conteos[
            ("POR_COBRAR", "ACTIVA")
        ],

        "monto_pendiente_por_pagar": str(
            por_pagar
        ),

        "monto_pendiente_por_cobrar": str(
            por_cobrar
        ),

        "criterio": (
            "Totales actuales de todas las "
            "obligaciones PostgreSQL, "
            "sin límite de 20 registros"
        ),

    }, conteos_presentes


def _filas_reservas_usuario(
    db: Session,
    id_usuario: int,
) -> list[dict]:

    return obtener_aportes_vinculados(
        db,
        id_usuario,
    )


def resumir_reservas(
    filas: list[dict],
) -> tuple[dict, dict]:

    pares = defaultdict(lambda: CERO)
    nombres = {}

    for f in filas:

        clave = (
            int(f["id_meta"]),
            int(f["id_cuenta"]),
        )

        if f["tipo"] not in (
            "RESERVA",
            "LIBERACION",
        ):
            raise HTTPException(
                409,
                "Tipo de aporte inconsistente",
            )

        delta = _decimal(f["monto"])

        if f["tipo"] == "LIBERACION":
            delta = -delta

        pares[clave] += delta

        nombres[clave] = (
            str(f["nombre_meta"]),
            str(f["nombre_cuenta"]),
        )

    if any(neto < CERO for neto in pares.values()):
        raise HTTPException(
            409,
            "Liberaciones superiores a reservas",
        )

    reservas = [
        {
            "id_meta": meta,
            "id_cuenta": cuenta,
            "nombre_meta": nombres[(meta, cuenta)][0],
            "nombre_cuenta": nombres[(meta, cuenta)][1],
            "reservado_neto": str(neto),
        }
        for (meta, cuenta), neto
        in sorted(pares.items())
        if neto > CERO
    ]

    return {
        "total_reservado_vinculado": str(
            sum(pares.values(), CERO)
        ),

        "numero_metas_con_reserva": len({
            r["id_meta"]
            for r in reservas
        }),

        "numero_relaciones_meta_cuenta": len(
            reservas
        ),

        "relaciones_meta_cuenta": reservas,

        "criterio": (
            "Reservas menos liberaciones activas, "
            "en todas las metas y cuentas"
        ),

    }, dict(pares)


def _consultar_tipos_obligacion_rdf(
    id_usuario: int,
) -> dict:

    try:
        return semrepo.contar_obligaciones_rdf(
            id_usuario,
            ejecutar=consultar_select,
        )

    except semrepo.EvidenciaSemanticaInvalida as error:
        raise HTTPException(
            409,
            str(error),
        ) from error


def _consultar_reservas_rdf(
    id_usuario: int,
) -> dict:

    try:
        return semrepo.reservas_netas_rdf(
            id_usuario,
            ejecutar=consultar_select,
        )

    except semrepo.EvidenciaSemanticaInvalida as error:
        raise HTTPException(
            409,
            str(error),
        ) from error


def _pares_desde_resumen(
    resumen: dict,
) -> dict:

    pares = {}

    for relacion in resumen["relaciones_meta_cuenta"]:

        clave = (
            int(relacion["id_meta"]),
            int(relacion["id_cuenta"]),
        )

        if clave in pares:
            raise HTTPException(
                409,
                "Relación financiera duplicada",
            )

        pares[clave] = _decimal(
            relacion["reservado_neto"]
        )

    return pares


def _sin_ceros(pares: dict) -> dict:
    return {
        clave: monto
        for clave, monto in pares.items()
        if monto != CERO
    }


def enriquecer_contexto_276(
    db: Session,
    id_usuario: int,
    contexto: dict,
) -> dict:

    semrepo._grafo(id_usuario)

    temas = set(
        contexto.get("temas_recuperados") or ()
    )

    if not temas.intersection({
        "metas",
        "obligaciones",
    }):
        return contexto

    analisis = contexto.setdefault(
        "analisis_financiero",
        {},
    )

    sql = contexto.get("postgresql", {})

    controles = contexto.setdefault(
        "fuseki",
        {},
    ).setdefault(
        "comprobaciones",
        {},
    )

    divergencias = []

    # --------------------------------------
    # OBLIGACIONES: REUTILIZAR EVIDENCIA
    # --------------------------------------

    if "obligaciones" in temas:

        if "obligaciones" in sql:
            obligaciones = sql["obligaciones"]

        else:
            # Compatibilidad con consumidores antiguos
            # que invocan directamente el enriquecedor.
            # El recuperador actualizado no necesita
            # ejecutar esta consulta adicional.
            plan = consultar_planificacion(
                db,
                id_usuario,
            )

            obligaciones = plan["obligaciones"]

        resumen, sql_counts = (
            resumir_obligaciones(obligaciones)
        )

        rdf_counts = {
            clave: cantidad
            for clave, cantidad in (
                _consultar_tipos_obligacion_rdf(
                    id_usuario
                ).items()
            )
            if cantidad > 0
        }

        consistente = sql_counts == rdf_counts

        analisis["obligaciones"] = resumen

        controles["tipos_obligaciones"] = {
            "coincide_con_postgresql": consistente,
            "total_en_fuseki": sum(
                rdf_counts.values()
            ),
        }

        if not consistente:
            divergencias.append(
                "Clasificación de obligaciones "
                "SQL/RDF diferente"
            )

    # --------------------------------------
    # RESERVAS: REUTILIZAR CÁLCULO EXISTENTE
    # --------------------------------------

    if "metas" in temas:

        if "reservas" in analisis:

            resumen = analisis["reservas"]

            sql_pares = _pares_desde_resumen(
                resumen
            )

        else:
            # Compatibilidad con llamadas anteriores.
            filas = _filas_reservas_usuario(
                db,
                id_usuario,
            )

            resumen, sql_pares = (
                resumir_reservas(filas)
            )

        rdf_pares = _consultar_reservas_rdf(
            id_usuario
        )

        consistente = (
            _sin_ceros(sql_pares)
            == _sin_ceros(rdf_pares)
        )

        analisis["reservas"] = resumen

        controles["reservas_meta_cuenta"] = {
            "coincide_con_postgresql": consistente,

            "numero_relaciones_en_fuseki": len(
                _sin_ceros(rdf_pares)
            ),
        }

        if not consistente:
            divergencias.append(
                "Reservas meta-cuenta "
                "SQL/RDF diferentes"
            )

    if divergencias:

        contexto.setdefault(
            "limitaciones",
            [],
        ).append(
            "Discrepancia semántica: "
            + "; ".join(divergencias)
            + ". Los importes PostgreSQL tienen "
            "prioridad; no usar RDF para "
            "importes actuales."
        )

    return contexto
