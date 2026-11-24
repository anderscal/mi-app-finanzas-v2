
"""Paso 27.4: pruebas aisladas de sincronización semántica.

No modifican cuentas reales ni contactan Fuseki.
"""

from unittest.mock import MagicMock

from app.models import (
    CuentaFinanciera,
    Movimiento,
    MetaFinanciera,
)

from app.services import (
    semantica_auto_sync as sync,
)


class SesionSimulada:

    def __init__(
        self,
        nuevos=(),
        cambios=(),
        borrados=(),
        propietarios=None,
    ):
        self.new = list(nuevos)
        self.dirty = list(cambios)
        self.deleted = list(borrados)

        self.info = {}

        self.propietarios = (
            propietarios or {}
        )

        self.escrituras = []

    def is_modified(
        self,
        obj,
        include_collections=False,
    ):
        return True

    def connection(self):
        return self

    def execute(
        self,
        sentencia,
        parametros=None,
    ):
        parametros = parametros or {}

        if "usuario" in parametros:
            self.escrituras.append(
                parametros["usuario"]
            )

            return MagicMock()

        resultado = MagicMock()

        cuenta_id = next(
            iter(self.propietarios),
            None,
        )

        resultado.scalar_one_or_none.return_value = (
            self.propietarios.get(
                cuenta_id
            )
        )

        return resultado


def test_274_detecta_cuenta_y_meta_mismo_usuario():
    sesion = SesionSimulada(
        nuevos=[
            CuentaFinanciera(id_usuario=8),
            MetaFinanciera(id_usuario=8),
        ]
    )

    assert sync._usuarios_afectados(
        sesion
    ) == {8}


def test_274_detecta_movimiento_por_propietario():
    sesion = SesionSimulada(
        nuevos=[
            Movimiento(id_cuenta=90),
        ],
        propietarios={
            90: 12,
        },
    )

    assert sync._usuarios_afectados(
        sesion
    ) == {12}


def test_274_marca_revision_una_vez(monkeypatch):
    monkeypatch.setenv(
        "SEMANTICA_AUTO_SYNC",
        "1",
    )

    sesion = SesionSimulada(
        nuevos=[
            CuentaFinanciera(id_usuario=8),
            MetaFinanciera(id_usuario=8),
        ]
    )

    sync._marcar_cambios(
        sesion,
        None,
        None,
    )

    assert sesion.escrituras == [8]

    assert sesion.info[
        sync.CLAVE_PENDIENTES
    ] == {8}


def test_274_rollback_limpia_pendientes(monkeypatch):
    monkeypatch.setenv(
        "SEMANTICA_AUTO_SYNC",
        "1",
    )

    sesion = SesionSimulada(
        nuevos=[
            CuentaFinanciera(id_usuario=8),
        ]
    )

    sync._marcar_cambios(
        sesion,
        None,
        None,
    )

    sync._limpiar_rollback(
        sesion
    )

    assert (
        sync.CLAVE_PENDIENTES
        not in sesion.info
    )


def test_274_publica_despues_de_commit(monkeypatch):
    monkeypatch.setenv(
        "SEMANTICA_AUTO_SYNC",
        "1",
    )

    publicados = []

    monkeypatch.setattr(
        sync,
        "sincronizar_usuario",
        publicados.append,
    )

    sesion = SesionSimulada()

    sesion.info[
        sync.CLAVE_PENDIENTES
    ] = {5, 2}

    sync._publicar_despues_de_commit(
        sesion
    )

    assert publicados == [2, 5]
    assert not sesion.info


def test_274_fallo_fuseki_no_revierte_commit(monkeypatch):
    monkeypatch.setenv(
        "SEMANTICA_AUTO_SYNC",
        "1",
    )

    def sin_fuseki(_):
        raise ConnectionError(
            "Falla simulada"
        )

    monkeypatch.setattr(
        sync,
        "sincronizar_usuario",
        sin_fuseki,
    )

    sesion = SesionSimulada()

    sesion.info[
        sync.CLAVE_PENDIENTES
    ] = {3}

    # El error no debe propagarse a una
    # operación SQL que ya hizo commit.
    sync._publicar_despues_de_commit(
        sesion
    )

    assert (
        sync.CLAVE_PENDIENTES
        not in sesion.info
    )


def test_274_no_activa_sin_configurar(monkeypatch):
    monkeypatch.delenv(
        "SEMANTICA_AUTO_SYNC",
        raising=False,
    )

    assert sync.habilitada() is False
