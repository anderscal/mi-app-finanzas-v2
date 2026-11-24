
"""Sincronización RDF con seguimiento transaccional.

La tabla estado_rdf_usuario se crea con la migración 001.

Los cambios financieros se confirman primero en PostgreSQL.
Fuseki se actualiza después del commit, mediante una
publicación idempotente de la instantánea del usuario.
"""

import logging
import os

from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.models import (
    CategoriaMovimiento,
    CuentaFinanciera,
    MetaFinanciera,
    Movimiento,
    ObligacionFinanciera,
    Presupuesto,
    Transferencia,
)
from app.models.aporte_meta import AporteMeta
from app.persistence.database import SesionFinanciera, engine


logger = logging.getLogger(__name__)

ESPACIO_BLOQUEO = 2740

CLAVE_PENDIENTES = "_rdf_usuarios_pendientes"

MODELOS_USUARIO = (
    CuentaFinanciera,
    CategoriaMovimiento,
    MetaFinanciera,
    ObligacionFinanciera,
    Presupuesto,
    AporteMeta,
)

MODELOS_CUENTA = (
    Movimiento,
    Transferencia,
)


def habilitada() -> bool:
    """La migración 001 debe ejecutarse antes de activar."""
    return os.getenv("SEMANTICA_AUTO_SYNC", "0") == "1"


def _usuarios_afectados(session: Session) -> set[int]:
    """Identifica propietarios a partir de objetos persistentes.

    El identificador del usuario no se recibe del frontend.
    Para movimientos y transferencias se obtiene de la
    cuenta financiera almacenada en PostgreSQL.
    """

    ids = set()
    vistos = set()
    propietarios = {}

    objetos = (
        *session.new,
        *session.dirty,
        *session.deleted,
    )

    for obj in objetos:
        if id(obj) in vistos:
            continue

        vistos.add(id(obj))

        if (
            obj in session.dirty
            and not session.is_modified(
                obj,
                include_collections=False,
            )
        ):
            continue

        if isinstance(obj, MODELOS_USUARIO):
            usuario_id = getattr(
                obj,
                "id_usuario",
                None,
            )

            if (
                type(usuario_id) is int
                and usuario_id > 0
            ):
                ids.add(usuario_id)

            continue

        if not isinstance(obj, MODELOS_CUENTA):
            continue

        if isinstance(obj, Movimiento):
            cuentas = (obj.id_cuenta,)
        else:
            cuentas = (
                obj.id_cuenta_origen,
                obj.id_cuenta_destino,
            )

        for cuenta_id in cuentas:
            if (
                type(cuenta_id) is not int
                or cuenta_id <= 0
            ):
                continue

            if cuenta_id not in propietarios:
                consulta = select(
                    CuentaFinanciera.id_usuario
                ).where(
                    CuentaFinanciera.id_cuenta
                    == cuenta_id
                )

                propietarios[cuenta_id] = (
                    session.connection()
                    .execute(consulta)
                    .scalar_one_or_none()
                )

            usuario_id = propietarios[cuenta_id]

            if (
                type(usuario_id) is int
                and usuario_id > 0
            ):
                ids.add(usuario_id)

    return ids


@event.listens_for(
    SesionFinanciera,
    "before_flush",
)
def _marcar_cambios(
    session,
    flush_context,
    instances,
):
    """Registra revisiones dentro de la transacción financiera."""

    if not habilitada():
        return

    usuarios = _usuarios_afectados(session)

    if not usuarios:
        return

    sentencia = text("""
        INSERT INTO estado_rdf_usuario (
            id_usuario,
            revision,
            revision_publicada,
            actualizacion_en
        )
        VALUES (
            :usuario,
            1,
            0,
            NOW()
        )
        ON CONFLICT (id_usuario)
        DO UPDATE SET
            revision = estado_rdf_usuario.revision + 1,
            actualizacion_en = NOW()
    """)

    for usuario_id in sorted(usuarios):
        session.connection().execute(
            sentencia,
            {"usuario": usuario_id},
        )

    session.info.setdefault(
        CLAVE_PENDIENTES,
        set(),
    ).update(usuarios)


@event.listens_for(
    SesionFinanciera,
    "after_rollback",
)
def _limpiar_rollback(session):
    """Descarta avisos de una operación que no se confirmó."""
    session.info.pop(
        CLAVE_PENDIENTES,
        None,
    )


@event.listens_for(
    SesionFinanciera,
    "after_commit",
)
def _publicar_despues_de_commit(session):
    """Publica RDF únicamente después del commit financiero."""

    usuarios = session.info.pop(
        CLAVE_PENDIENTES,
        set(),
    )

    if not habilitada():
        return

    for usuario_id in sorted(usuarios):
        try:
            sincronizado = sincronizar_usuario(
                usuario_id
            )

            if not sincronizado:
                logger.warning(
                    "Publicación RDF todavía pendiente "
                    "para usuario_id=%s",
                    usuario_id,
                )

        except Exception:
            # El commit de PostgreSQL ya ocurrió.
            # Nunca debemos informar que falló la
            # operación financiera por un error de Fuseki.
            logger.exception(
                "Publicación RDF pendiente para "
                "usuario_id=%s; PostgreSQL conserva "
                "la revisión para reintentar",
                usuario_id,
            )


def sincronizar_usuario(
    id_usuario: int,
) -> bool:
    """Publica la revisión RDF pendiente de un usuario.

    El grafo se reemplaza de forma idempotente.
    El bloqueo transaccional evita dos publicaciones
    simultáneas para el mismo usuario.

    True: revisión publicada.
    False: hubo cambios concurrentes repetidos.
    """

    if (
        type(id_usuario) is not int
        or id_usuario <= 0
    ):
        raise ValueError(
            "Identificador de usuario inválido"
        )

    if not habilitada():
        return True

    # Session base evita ejecutar nuevamente los
    # eventos de SesionFinanciera.
    with Session(engine) as db:

        db.execute(
            text(
                "SELECT pg_advisory_xact_lock("
                ":espacio, :usuario)"
            ),
            {
                "espacio": ESPACIO_BLOQUEO,
                "usuario": id_usuario,
            },
        )

        for _ in range(3):

            estado = db.execute(
                text("""
                    SELECT
                        revision,
                        revision_publicada
                    FROM estado_rdf_usuario
                    WHERE id_usuario = :usuario
                """),
                {"usuario": id_usuario},
            ).mappings().first()

            if estado is None:
                # También permite crear el grafo de
                # un usuario que aún no tiene operaciones.
                db.execute(
                    text("""
                        INSERT INTO estado_rdf_usuario (
                            id_usuario,
                            revision,
                            revision_publicada
                        )
                        VALUES (:usuario, 1, 0)
                        ON CONFLICT (id_usuario)
                        DO NOTHING
                    """),
                    {"usuario": id_usuario},
                )

                continue

            revision = int(
                estado["revision"]
            )

            revision_publicada = int(
                estado["revision_publicada"]
            )

            if revision_publicada >= revision:
                db.commit()
                return True

            from app.business.semantica_service import (
                construir_grafo_usuario,
                iri_grafo,
            )
            from app.services.fuseki_client import (
                publicar_grafo,
            )

            grafo, _ = construir_grafo_usuario(
                db,
                id_usuario,
            )

            publicar_grafo(
                grafo,
                iri_grafo(id_usuario),
            )

            actualizado = db.execute(
                text("""
                    UPDATE estado_rdf_usuario
                    SET
                        revision_publicada = :revision,
                        publicacion_en = NOW()
                    WHERE id_usuario = :usuario
                      AND revision = :revision
                      AND revision_publicada < :revision
                """),
                {
                    "usuario": id_usuario,
                    "revision": revision,
                },
            )

            if actualizado.rowcount == 1:
                db.commit()
                return True

            # Un nuevo commit financiero modificó
            # la revisión durante la publicación.
            # Volvemos a leer PostgreSQL y publicar.

        db.rollback()
        return False


def asegurar_actualizacion_para_rag(
    db: Session,
    id_usuario: int,
) -> None:
    """Repara revisiones pendientes antes de consultar SPARQL.

    Las sesiones de pruebas que utilizan Session base
    conservan los simuladores existentes.
    """

    if not habilitada():
        return

    if not isinstance(
        db,
        SesionFinanciera,
    ):
        return

    if not sincronizar_usuario(id_usuario):
        raise RuntimeError(
            "La revisión semántica cambió "
            "durante su publicación"
        )
