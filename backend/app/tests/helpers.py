from decimal import Decimal

from sqlalchemy import select

from app.models import (
    CategoriaMovimiento,
    CuentaFinanciera,
    Usuario,
)


def crear_usuario_autenticado(
    client,
    db_session,
    email: str,
    password: str = "PasswordPrueba2026!"
):
    respuesta = client.post(
        "/auth/registro",
        json={
            "nombre_1": "Usuario",
            "nombre_2": None,
            "apellido_1": "Prueba",
            "apellido_2": None,
            "email": email,
            "password": password
        }
    )

    assert respuesta.status_code == 201

    id_usuario = respuesta.json()["id_usuario"]

    usuario = db_session.get(
        Usuario,
        id_usuario
    )

    login = client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password
        }
    )

    assert login.status_code == 200

    token = login.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    return usuario, headers


def crear_cuenta(
    db_session,
    id_usuario: int,
    nombre: str,
    saldo_inicial: str
):
    cuenta = CuentaFinanciera(
        id_usuario=id_usuario,
        nombre_cuenta=nombre,
        tipo_cuenta="AHORROS",
        institucion="Banco pytest",
        saldo_inicial=Decimal(saldo_inicial),
        estado="ACTIVA"
    )

    db_session.add(cuenta)
    db_session.commit()

    return cuenta


def obtener_categoria_sistema(
    db_session,
    tipo: str
):
    categoria = db_session.scalar(
        select(CategoriaMovimiento)
        .where(
            CategoriaMovimiento.es_sistema.is_(True),
            CategoriaMovimiento.tipo_categoria == tipo,
            CategoriaMovimiento.estado == "ACTIVA"
        )
        .order_by(
            CategoriaMovimiento.id_categoria
        )
    )

    assert categoria is not None

    return categoria