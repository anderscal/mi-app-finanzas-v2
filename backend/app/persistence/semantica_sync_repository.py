"""Persistencia transaccional de revisiones RDF."""

from sqlalchemy import select, text
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

from app.persistence.database import (
    SesionFinanciera,
    engine,
)


ESPACIO_BLOQUEO = 2740

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


def es_sesion_financiera(db):

    return isinstance(
        db,
        SesionFinanciera,
    )


def abrir_sesion_publicacion():

    return Session(engine)


def usuarios_afectados(session):

    ids = set()
    vistos = set()
    propietarios = {}

    for obj in (
        *session.new,
        *session.dirty,
        *session.deleted,
    ):

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

            uid = getattr(
                obj,
                "id_usuario",
                None,
            )

            if type(uid) is int and uid > 0:
                ids.add(uid)

            continue

        if not isinstance(
            obj,
            MODELOS_CUENTA,
        ):
            continue

        cuentas = (
            (obj.id_cuenta,)
            if isinstance(obj, Movimiento)
            else (
                obj.id_cuenta_origen,
                obj.id_cuenta_destino,
            )
        )

        for cid in cuentas:

            if type(cid) is not int or cid <= 0:
                continue

            if cid not in propietarios:

                consulta = select(
                    CuentaFinanciera.id_usuario
                ).where(
                    CuentaFinanciera.id_cuenta == cid
                )

                propietarios[cid] = (
                    session.connection()
                    .execute(consulta)
                    .scalar_one_or_none()
                )

            uid = propietarios[cid]

            if type(uid) is int and uid > 0:
                ids.add(uid)

    return ids


def marcar_revisiones(
    session,
    usuarios,
):

    sentencia = text("""
        INSERT INTO estado_rdf_usuario (
            id_usuario,
            revision,
            revision_publicada,
            actualizacion_en
        )
        VALUES (:usuario, 1, 0, NOW())

        ON CONFLICT (id_usuario)
        DO UPDATE SET
            revision = estado_rdf_usuario.revision + 1,
            actualizacion_en = NOW()
    """)

    for uid in sorted(usuarios):

        session.connection().execute(
            sentencia,
            {"usuario": uid},
        )


def bloquear_publicacion(
    db,
    uid,
):

    db.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            ":espacio, :usuario)"
        ),

        {
            "espacio": ESPACIO_BLOQUEO,
            "usuario": uid,
        },
    )


def leer_estado(
    db,
    uid,
):

    return db.execute(
        text("""
            SELECT
                revision,
                revision_publicada,

                COALESCE(
                    publicacion_en >=
                        clock_timestamp() - INTERVAL '24 hours'

                    AND publicacion_en <= clock_timestamp(),

                    FALSE
                ) AS reciente

            FROM estado_rdf_usuario

            WHERE id_usuario = :usuario
        """),

        {"usuario": uid},

    ).mappings().first()


def crear_estado(
    db,
    uid,
):

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

        {"usuario": uid},
    )


def confirmar_publicacion(
    db,
    uid,
    revision,
):

    resultado = db.execute(
        text("""
            UPDATE estado_rdf_usuario

            SET
                revision_publicada = :revision,
                publicacion_en = clock_timestamp()

            WHERE id_usuario = :usuario

              AND revision = :revision

              AND revision_publicada <= :revision
        """),

        {
            "usuario": uid,
            "revision": revision,
        },
    )

    return resultado.rowcount == 1