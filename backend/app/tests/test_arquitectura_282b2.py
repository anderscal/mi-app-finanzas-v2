"""Pruebas de regresion del Paso 28.2 B.2."""

from datetime import (
    datetime,
    timezone,
)

from unittest.mock import MagicMock

import pytest

from app.business import (
    semantica_auto_sync as sync,
)

from app.business import (
    rag_retrieval_service as retrieval,
)

from app.persistence import (
    semantica_consulta_repository as consultas,
)


@pytest.fixture
def publicacion(monkeypatch):

    db = MagicMock()

    repo = MagicMock()

    repo.leer_estado.return_value = {

        "revision": 14,

        "revision_publicada": 14,

        "reciente": True,
    }

    repo.confirmar_publicacion.return_value = True

    construir = MagicMock(
        return_value=(
            [1, 2],
            {"cuentas": 1},
        )
    )

    publicar = MagicMock()

    monkeypatch.setattr(
        sync,
        "repo",
        repo,
    )

    monkeypatch.setattr(
        sync,
        "construir_grafo_usuario",
        construir,
    )

    monkeypatch.setattr(
        sync,
        "publicar_grafo",
        publicar,
    )

    return (
        db,
        repo,
        construir,
        publicar,
    )


def test_282b2_reciente_no_republica(
    publicacion,
):

    db, repo, construir, publicar = publicacion

    assert sync.publicar_revision(
        db,
        7,
    ) == {
        "sin_cambios": True,
    }

    repo.bloquear_publicacion.assert_called_once_with(
        db,
        7,
    )

    construir.assert_not_called()

    publicar.assert_not_called()

    db.commit.assert_called_once()


def test_282b2_antigua_renueva_misma_revision(
    publicacion,
):

    db, repo, construir, publicar = publicacion

    repo.leer_estado.return_value[
        "reciente"
    ] = False

    assert sync.publicar_revision(
        db,
        7,
    )["triples"] == 2

    publicar.assert_called_once_with(
        [1, 2],
        sync.iri_grafo(7),
    )

    repo.confirmar_publicacion.assert_called_once_with(
        db,
        7,
        14,
    )

    db.commit.assert_called_once()


def test_282b2_manual_forzada(
    publicacion,
):

    db, repo, construir, publicar = publicacion

    assert sync.publicar_revision(
        db,
        7,
        forzar=True,
    )["entidades"] == {
        "cuentas": 1,
    }

    publicar.assert_called_once()

    db.commit.assert_called_once()


def test_282b2_revision_concurrente(
    publicacion,
):

    db, repo, construir, publicar = publicacion

    repo.leer_estado.side_effect = [

        {
            "revision": 14,
            "revision_publicada": 13,
            "reciente": True,
        },

        {
            "revision": 15,
            "revision_publicada": 13,
            "reciente": True,
        },
    ]

    repo.confirmar_publicacion.side_effect = [
        False,
        True,
    ]

    assert sync.publicar_revision(
        db,
        7,
    )["triples"] == 2

    assert publicar.call_count == 2

    assert (
        repo.confirmar_publicacion.call_args.args
        == (db, 7, 15)
    )

    db.commit.assert_called_once()


def test_282b2_fallo_no_confirma(
    publicacion,
):

    db, repo, construir, publicar = publicacion

    publicar.side_effect = ConnectionError(
        "Fallo simulado"
    )

    with pytest.raises(ConnectionError):

        sync.publicar_revision(
            db,
            7,
            forzar=True,
        )

    repo.confirmar_publicacion.assert_not_called()

    db.commit.assert_not_called()

    db.rollback.assert_called_once()


def test_282b2_rag_renueva_y_verifica(
    monkeypatch,
):

    consultar = MagicMock(
        side_effect=[

            {
                "fecha_instantanea":
                    "2020-01-01T00:00:00+00:00",
            },

            {
                "fecha_instantanea":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),
            },
        ]
    )

    renovar = MagicMock(
        return_value=True
    )

    monkeypatch.setattr(
        retrieval,

        "asegurar_actualizacion_para_rag",

        lambda *a: None,
    )

    monkeypatch.setattr(
        retrieval,

        "obtener_contexto_semantico_basico",

        consultar,
    )

    monkeypatch.setattr(
        retrieval,

        "renovar_para_rag",

        renovar,
    )

    db = object()

    assert retrieval._preparar_semantica(
        db,
        7,
    )["vigencia"] == "RECIENTE"

    renovar.assert_called_once_with(
        db,
        7,
    )

    assert consultar.call_count == 2


def test_282b2_rag_rechaza_si_sigue_antigua(
    monkeypatch,
):

    monkeypatch.setattr(
        retrieval,

        "asegurar_actualizacion_para_rag",

        lambda *a: None,
    )

    monkeypatch.setattr(
        retrieval,

        "obtener_contexto_semantico_basico",

        lambda **kw: {
            "fecha_instantanea":
                "2020-01-01T00:00:00+00:00",
        },
    )

    monkeypatch.setattr(
        retrieval,

        "renovar_para_rag",

        lambda *a: True,
    )

    with pytest.raises(
        retrieval.ErrorRAG
    ) as exc:

        retrieval._preparar_semantica(
            object(),
            7,
        )

    assert exc.value.codigo == 409


def test_282b2_sparql_grafo_propio(
    monkeypatch,
):

    ejecutar = MagicMock(
        return_value=[]
    )

    monkeypatch.setattr(
        consultas,

        "consultar_select",

        ejecutar,
    )

    assert consultas.obtener_filas_cuentas(
        7
    ) == []

    assert (
        "GRAPH <urn:finanzas:grafo:usuario:7>"
        in ejecutar.call_args.args[0]
    )

    with pytest.raises(ValueError):

        consultas.obtener_filas_cuentas(
            "7> GRAPH ?g"
        )

    ejecutar.assert_called_once()