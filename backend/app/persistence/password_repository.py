from sqlalchemy import func, select, update

from app.models import (
    Usuario,
    TokenRecuperacion,
)


def bloquear_usuario_auth(db, uid):

    return db.scalar(
        select(Usuario)
        .where(Usuario.id_usuario == uid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def ultima_expiracion_y_cantidad(db, uid, ahora):

    return db.execute(
        select(
            func.max(
                TokenRecuperacion.fecha_expiracion
            ),
            func.count(
                TokenRecuperacion.id_token
            ),
        )
        .where(
            TokenRecuperacion.id_usuario == uid,
            TokenRecuperacion.fecha_expiracion > ahora,
        )
    ).one()


def insertar_token(db, uid, huella, expira):

    db.add(
        TokenRecuperacion(
            id_usuario=uid,
            token_hash=huella,
            fecha_expiracion=expira,
            usado=False,
        )
    )


def propietario_token(db, huella):

    return db.scalar(
        select(TokenRecuperacion.id_usuario)
        .where(
            TokenRecuperacion.token_hash == huella
        )
    )


def bloquear_token(db, uid, huella):

    return db.scalar(
        select(TokenRecuperacion)
        .where(
            TokenRecuperacion.id_usuario == uid,
            TokenRecuperacion.token_hash == huella,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def invalidar_tokens(db, uid):

    db.execute(
        update(TokenRecuperacion)
        .where(
            TokenRecuperacion.id_usuario == uid,
            TokenRecuperacion.usado.is_(False),
        )
        .values(usado=True)
    )


def actualizar_password(db, usuario, nuevo_hash):

    usuario.password_hash = nuevo_hash

    usuario.version_sesion += 1

    invalidar_tokens(
        db,
        usuario.id_usuario,
    )