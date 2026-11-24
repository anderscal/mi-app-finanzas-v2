
"""Regresion del contrato RAG dinamico.

Pasos 27.9 A.1 y A.2.
Sin llamadas reales a Gemini, PostgreSQL o Fuseki.
"""

import pytest

from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.business.rag_contrato import (
    CATALOGO,
    CAMPOS_PREDETERMINADOS,
    Consulta,
    PlanConsulta,
    preparar_consulta,
    declaracion_herramienta,
)

from app.business.rag_contexto_ia import (
    RegistroAlias,
)

from app.persistence.rag_consulta_repository import (
    construir_select,
)


# ======================================
# PRUEBAS ANTERIORES - PASO 27.9 A.1
# ======================================

@pytest.mark.parametrize(
    "entidad",
    list(CATALOGO),
)
def test_279a1_listados_sin_campos(entidad):

    consulta = Consulta(
        entidad=entidad,
        operacion="listar",
    )

    assert consulta.campos == list(
        CAMPOS_PREDETERMINADOS[entidad]
    )

    assert 1 <= len(consulta.campos) <= 8

    assert all(
        campo in CATALOGO[entidad]
        for campo in consulta.campos
    )

    assert "id_usuario" not in consulta.campos
    assert "password" not in consulta.campos


def test_279a1_plan_presupuestos_reportado():

    plan = PlanConsulta.model_validate({
        "estado": "consultar",

        "consultas": [{
            "entidad": "presupuestos",
            "operacion": "listar",

            "filtros": [
                {
                    "campo": "anio",
                    "operador": "igual",
                    "valor": "2026",
                },
                {
                    "campo": "mes",
                    "operador": "igual",
                    "valor": "11",
                },
            ],
        }],
    })

    consulta = preparar_consulta(
        plan.consultas[0],
        lambda valor: valor,
    )

    assert consulta["campos"] == [
        "categoria",
        "anio",
        "mes",
        "limite",
        "gastado",
        "disponible",
        "porcentaje_usado",
    ]

    assert consulta["filtros"] == [
        {
            "campo": "anio",
            "operador": "igual",
            "valor": 2026,
        },
        {
            "campo": "mes",
            "operador": "igual",
            "valor": 11,
        },
    ]


def test_279a1_proyeccion_explicita_conservada():

    consulta = Consulta(
        entidad="cuentas",
        operacion="listar",
        campos=["nombre", "saldo_libre"],
    )

    assert consulta.campos == [
        "nombre",
        "saldo_libre",
    ]


def test_279a1_lista_campos_vacia():

    consulta = Consulta(
        entidad="metas",
        operacion="listar",
        campos=[],
    )

    assert consulta.campos == list(
        CAMPOS_PREDETERMINADOS["metas"]
    )


def test_279a1_agregacion_sin_proyeccion():

    consulta = Consulta(
        entidad="cuentas",
        operacion="sumar",
        campo="saldo_libre",
    )

    assert consulta.campos == []
    assert consulta.campo == "saldo_libre"


def test_279a1_agregacion_sin_campo_rechazada():

    with pytest.raises(ValidationError):

        Consulta(
            entidad="cuentas",
            operacion="sumar",
        )


def test_279a1_no_permite_campos_privados():

    with pytest.raises(ValidationError):

        Consulta(
            entidad="cuentas",
            operacion="listar",
            campos=["nombre", "id_usuario"],
        )


def test_279a1_no_permite_cambiar_usuario():

    with pytest.raises(ValidationError):

        Consulta.model_validate({
            "entidad": "cuentas",
            "operacion": "listar",
            "id_usuario": 999,
        })


def test_279a1_no_permite_escrituras():

    with pytest.raises(ValidationError):

        Consulta.model_validate({
            "entidad": "movimientos",
            "operacion": "eliminar",
        })


def test_279a1_contrato_gemini_documenta_campos():

    herramienta = declaracion_herramienta()

    consulta = herramienta[
        "parameters"
    ]["properties"]["consultas"]["items"]

    descripcion = consulta[
        "properties"
    ]["campos"]["description"]

    assert "predeterminados" in descripcion

    assert "campos" not in consulta["required"]


# ======================================
# NUEVAS PRUEBAS - PASO 27.9 A.2
# ======================================

@pytest.mark.parametrize(
    "operacion",
    [
        "sumar",
        "promedio",
        "minimo",
        "maximo",
    ],
)
def test_279a2_normaliza_orden_agregado(operacion):

    consulta = Consulta(
        entidad="movimientos",

        operacion=operacion,

        campo="monto",

        agrupar_por=["categoria"],

        orden_campo="monto",

        limite=5,

        filtros=[
            {
                "campo": "tipo",
                "operador": "igual",
                "valor": "GASTO",
            },
            {
                "campo": "origen",
                "operador": "igual",
                "valor": "NORMAL",
            },
            {
                "campo": "estado",
                "operador": "igual",
                "valor": "ACTIVO",
            },
        ],
    )

    assert consulta.orden_campo == "valor"

    assert consulta.descendente is True

    assert consulta.campo == "monto"

    assert consulta.agrupar_por == ["categoria"]

    assert len(consulta.filtros) == 3


def test_279a2_respeta_orden_ascendente_explicito():

    consulta = Consulta(
        entidad="movimientos",

        operacion="sumar",

        campo="monto_con_gmf",

        agrupar_por=["categoria"],

        orden_campo="monto_con_gmf",

        descendente=False,
    )

    assert consulta.orden_campo == "valor"

    assert consulta.descendente is False


def test_279a2_conserva_orden_por_grupo():

    consulta = Consulta(
        entidad="movimientos",

        operacion="sumar",

        campo="monto",

        agrupar_por=["categoria"],

        orden_campo="categoria",
    )

    assert consulta.orden_campo == "categoria"

    assert consulta.descendente is False


def test_279a2_rechaza_orden_no_autorizado():

    with pytest.raises(ValidationError):

        Consulta(
            entidad="movimientos",

            operacion="sumar",

            campo="monto",

            agrupar_por=["categoria"],

            orden_campo="id_usuario",
        )


def test_279a2_no_agrega_orden_si_no_se_solicita():

    consulta = Consulta(
        entidad="cuentas",

        operacion="sumar",

        campo="saldo_libre",
    )

    assert consulta.orden_campo == ""

    assert consulta.descendente is False


def test_279a2_restaura_alias_con_espacios():

    registro = RegistroAlias([
        "Cuenta financiera privada",
    ])

    alias = registro.proteger(
        "Cuenta financiera privada"
    )

    deformado = alias.replace(
        "privada",
        "priv ada",
    )

    assert deformado != alias

    respuesta = registro.restaurar_filtro(
        f"Movimiento en {deformado}. [E1]"
    )

    assert respuesta == (
        "Movimiento en Cuenta financiera privada. [E1]"
    )


def test_279a2_alias_desconocido_rechazado():

    registro = RegistroAlias([
        "Cuenta financiera privada",
    ])

    with pytest.raises(ValueError):

        registro.restaurar_filtro(
            "Entidad_priv ada_99999"
        )


def test_279a2_sql_compila_orden_normalizado():

    consulta = Consulta(
        entidad="movimientos",

        operacion="sumar",

        campo="monto",

        agrupar_por=["categoria"],

        orden_campo="monto",

        limite=5,
    )

    plan = preparar_consulta(
        consulta,
        lambda valor: valor,
    )

    sentencia = construir_select(
        7,
        plan,
    )

    sql = str(
        sentencia.compile(
            dialect=postgresql.dialect()
        )
    ).upper()

    assert sentencia.is_select

    assert "SUM(" in sql

    assert "GROUP BY" in sql

    assert "ORDER BY" in sql

    assert "DESC" in sql.rsplit(
        "ORDER BY",
        1,
    )[1]

    assert plan["orden_campo"] == "valor"
