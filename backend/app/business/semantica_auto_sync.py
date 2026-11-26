"""Orquestacion de la proyeccion RDF. Business."""

import logging
import os

from app.persistence import (
    semantica_sync_repository as repo,
)

from app.persistence.fuseki_client import (
    publicar_grafo,
)

from app.business.semantica_service import (
    construir_grafo_usuario,
    iri_grafo,
)


logger = logging.getLogger(__name__)

CLAVE_PENDIENTES = "_rdf_usuarios_pendientes"


def habilitada():

    return (
        os.getenv(
            "SEMANTICA_AUTO_SYNC",
            "0",
        ) == "1"
    )


def _usuarios_afectados(session):

    return repo.usuarios_afectados(
        session
    )


def _marcar_cambios(
    session,
    flush_context,
    instances,
):

    if not habilitada():
        return

    usuarios = _usuarios_afectados(
        session
    )

    if usuarios:

        repo.marcar_revisiones(
            session,
            usuarios,
        )

        session.info.setdefault(
            CLAVE_PENDIENTES,
            set(),
        ).update(usuarios)


def _limpiar_rollback(session):

    session.info.pop(
        CLAVE_PENDIENTES,
        None,
    )


def _publicar_despues_de_commit(session):

    usuarios = session.info.pop(
        CLAVE_PENDIENTES,
        set(),
    )

    if not habilitada():
        return

    for uid in sorted(usuarios):

        try:

            if not sincronizar_usuario(uid):

                logger.warning(
                    "Publicacion RDF pendiente "
                    "para usuario_id=%s",

                    uid,
                )

        except Exception:

            logger.exception(
                "Publicacion RDF pendiente "
                "para usuario_id=%s; "
                "PostgreSQL conserva la revision "
                "para reintentar",

                uid,
            )


def publicar_revision(
    db,
    uid,
    *,
    forzar=False,
):

    iri = iri_grafo(uid)

    try:

        repo.bloquear_publicacion(
            db,
            uid,
        )

        for _ in range(3):

            estado = repo.leer_estado(
                db,
                uid,
            )

            if estado is None:

                repo.crear_estado(
                    db,
                    uid,
                )

                continue

            revision = int(
                estado["revision"]
            )

            if (
                not forzar

                and int(
                    estado["revision_publicada"]
                ) == revision

                and estado["reciente"]
            ):

                db.commit()

                return {
                    "sin_cambios": True,
                }

            grafo, conteos = construir_grafo_usuario(
                db,
                uid,
            )

            publicar_grafo(
                grafo,
                iri,
            )

            if repo.confirmar_publicacion(
                db,
                uid,
                revision,
            ):

                db.commit()

                return {
                    "triples": len(grafo),
                    "entidades": conteos,
                }

        db.rollback()

        return None

    except Exception:

        db.rollback()

        raise


def sincronizar_usuario(
    id_usuario,
    *,
    forzar=False,
):

    # Valida el identificador antes de operar.

    iri_grafo(id_usuario)

    if not habilitada():
        return True

    with repo.abrir_sesion_publicacion() as db:

        return publicar_revision(
            db,
            id_usuario,
            forzar=forzar,
        ) is not None


def asegurar_actualizacion_para_rag(
    db,
    id_usuario,
):

    if (
        habilitada()
        and repo.es_sesion_financiera(db)
    ):

        if not sincronizar_usuario(id_usuario):

            raise RuntimeError(
                "La revision semantica cambio "
                "durante su publicacion"
            )


def renovar_para_rag(
    db,
    id_usuario,
):

    if (
        not habilitada()

        or not repo.es_sesion_financiera(db)
    ):

        return False

    if not sincronizar_usuario(
        id_usuario,
        forzar=True,
    ):

        raise RuntimeError(
            "No fue posible renovar "
            "la instantanea RDF"
        )

    return True