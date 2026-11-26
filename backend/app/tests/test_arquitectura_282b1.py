"""Pruebas de persistencia y arquitectura.

Paso 28.2 B.1.

No necesitan ejecutar consultas reales contra PostgreSQL,
Fuseki ni Gemini.
"""

import ast

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sqlalchemy.dialects import postgresql

from app.models import Transferencia

from app.persistence import (
    semantica_exportacion_repository as exportacion,
)

from app.persistence.anulacion_repository import (
    consultar_movimiento_usuario,
    consultar_transferencia,
)

from app.persistence.usuario_repository import (
    bloquear_usuario,
)


APP = Path(
    __file__
).resolve().parents[1]


def _compilar_sql(sentencia):

    return str(
        sentencia.compile(
            dialect=postgresql.dialect(),

            compile_kwargs={
                "literal_binds": True,
            },
        )
    ).upper()


# ========================================
# SEPARACION BUSINESS - PERSISTENCE
# ========================================

@pytest.mark.parametrize(
    "archivo",
    [
        "anulacion_service.py",
        "categoria_service.py",
        "semantica_service.py",
    ],
)
def test_282b1_business_sin_consultas_directas(
    archivo,
):

    ruta = APP / "business" / archivo

    arbol = ast.parse(
        ruta.read_text(
            encoding="utf-8-sig"
        )
    )

    operaciones_sql = {
        "select",
        "text",
        "insert",
        "update",
        "delete",
    }

    metodos_consulta = {
        "execute",
        "scalar",
        "scalars",
        "query",
        "get",
    }

    for nodo in ast.walk(arbol):

        if isinstance(nodo, ast.ImportFrom):

            if nodo.module == "sqlalchemy":

                assert not any(

                    alias.name in operaciones_sql

                    for alias in nodo.names

                ), archivo

        if isinstance(nodo, ast.Call):

            funcion = nodo.func

            if isinstance(
                funcion,
                ast.Name,
            ):

                assert (
                    funcion.id
                    not in operaciones_sql
                ), archivo

            if isinstance(
                funcion,
                ast.Attribute,
            ) and isinstance(
                funcion.value,
                ast.Name,
            ):

                assert not (
                    funcion.value.id == "db"
                    and funcion.attr
                    in metodos_consulta
                ), archivo


# ========================================
# EXPORTACION RDF
# ========================================

@pytest.mark.parametrize(
    "funcion, tabla_propietaria",
    [
        (
            "obtener_cuentas",
            "cuenta_financiera",
        ),
        (
            "obtener_metas",
            "meta_financiera",
        ),
        (
            "obtener_obligaciones",
            "obligacion_financiera",
        ),
        (
            "obtener_aportes",
            "aporte_meta",
        ),
        (
            "obtener_categorias",
            "categoria_movimiento",
        ),
        (
            "obtener_movimientos",
            "cuenta_financiera",
        ),
        (
            "obtener_transferencias",
            "cuenta_financiera",
        ),
        (
            "obtener_presupuestos",
            "presupuesto",
        ),
    ],
)
def test_282b1_exportacion_restringe_usuario(
    funcion,
    tabla_propietaria,
):

    db = MagicMock()

    db.scalars.return_value = []

    recuperar = getattr(
        exportacion,
        funcion,
    )

    filas = recuperar(
        db,
        37,
    )

    assert filas == []

    db.scalars.assert_called_once()

    sentencia = (
        db.scalars.call_args.args[0]
    )

    sql = _compilar_sql(
        sentencia
    )

    assert sentencia.is_select

    assert (
        f"{tabla_propietaria.upper()}.ID_USUARIO = 37"
        in sql
    )

    assert "ORDER BY" in sql

    if funcion == "obtener_categorias":

        assert (
            "ES_SISTEMA IS TRUE"
            in sql
        )

    if funcion in {
        "obtener_movimientos",
        "obtener_transferencias",
    }:

        assert "JOIN" in sql

    db.commit.assert_not_called()

    db.rollback.assert_not_called()


# ========================================
# BLOQUEOS Y ANULACIONES
# ========================================

def test_282b1_bloqueo_usuario():

    db = MagicMock()

    bloquear_usuario(
        db,
        37,
    )

    db.scalar.assert_called_once()

    sentencia = (
        db.scalar.call_args.args[0]
    )

    sql = _compilar_sql(
        sentencia
    )

    assert sentencia.is_select

    assert (
        "USUARIO.ID_USUARIO = 37"
        in sql
    )

    assert "FOR UPDATE" in sql

    db.commit.assert_not_called()


def test_282b1_movimiento_propietario():

    db = MagicMock()

    consultar_movimiento_usuario(
        db,
        37,
        81,
    )

    db.scalar.assert_called_once()

    sentencia = (
        db.scalar.call_args.args[0]
    )

    sql = _compilar_sql(
        sentencia
    )

    assert sentencia.is_select

    assert (
        "MOVIMIENTO.ID_MOVIMIENTO = 81"
        in sql
    )

    assert (
        "CUENTA_FINANCIERA.ID_USUARIO = 37"
        in sql
    )

    assert "JOIN" in sql

    # La consulta inicial no bloquea.
    # Business coordina posteriormente los bloqueos.

    assert "FOR UPDATE" not in sql

    db.commit.assert_not_called()


def test_282b1_lectura_transferencia():

    db = MagicMock()

    resultado = consultar_transferencia(
        db,
        81,
    )

    db.get.assert_called_once_with(
        Transferencia,
        81,
    )

    assert resultado is db.get.return_value

    db.commit.assert_not_called()

    db.rollback.assert_not_called()