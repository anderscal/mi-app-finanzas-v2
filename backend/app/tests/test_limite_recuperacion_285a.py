import pytest

from sqlalchemy import text

from app.business import password_service as servicio

from app.services import (
    correo_recuperacion_service as correo,
)


@pytest.fixture
def cupo(db_session):

    # El fixture general mantiene la prueba
    # dentro de una transaccion independiente.

    db_session.execute(
        text("""
            DELETE FROM public.limite_recuperacion
        """)
    )

    db_session.commit()

    return db_session


@pytest.fixture
def correo_simulado(monkeypatch):

    envios = []

    monkeypatch.setattr(
        correo,

        "obtener_configuracion",

        lambda: (
            "clave-ficticia",
            "qa@example.com",
            "http://127.0.0.1:5500",
        ),
    )

    monkeypatch.setattr(
        correo,

        "enviar_enlace",

        lambda config, email, token:
            envios.append(email),
    )

    return envios


def solicitar(
    client,
    email="qa.inexistente285@example.com",
):

    return client.post(
        "/auth/solicitar-recuperacion",

        json={
            "email": email,
        },
    )


def cantidad(db):

    return db.scalar(
        text("""
            SELECT COUNT(*)
            FROM public.limite_recuperacion
        """)
    )


def preparar_registros(db, total, minutos):

    db.execute(
        text("""
            INSERT INTO public.limite_recuperacion
                (fecha)

            SELECT
                clock_timestamp()
                - make_interval(mins => :minutos)

            FROM generate_series(1, :total)
        """),
        {
            "total": total,
            "minutos": minutos,
        },
    )

    db.commit()


# ======================================
# 1. LIMITE GLOBAL DE 15 MINUTOS
# ======================================

def test_limite_15_minutos(
    client,
    cupo,
    correo_simulado,
):

    for i in range(20):

        respuesta = solicitar(
            client,
            f"qa.inexistente{i}@example.com",
        )

        assert respuesta.status_code == 202

    assert cantidad(cupo) == 20

    respuesta = solicitar(client)

    assert respuesta.status_code == 429

    assert cantidad(cupo) == 20

    assert not correo_simulado


# ======================================
# 2. LIMITE GLOBAL DE 24 HORAS
# ======================================

def test_limite_24_horas(
    client,
    cupo,
    correo_simulado,
):

    preparar_registros(
        cupo,
        total=200,
        minutos=60,
    )

    respuesta = solicitar(client)

    assert respuesta.status_code == 429

    assert cantidad(cupo) == 200

    assert not correo_simulado


# ======================================
# 3. LIBERACION DE CUPOS ANTIGUOS
# ======================================

def test_registros_expirados(
    client,
    cupo,
    correo_simulado,
):

    preparar_registros(
        cupo,
        total=200,
        minutos=1500,
    )

    respuesta = solicitar(client)

    assert respuesta.status_code == 202

    assert cantidad(cupo) == 1

    assert not correo_simulado


# ======================================
# 4. BLOQUEO ANTES DE CONSULTAR USUARIOS
# ======================================

def test_limite_no_busca_usuario(
    client,
    cupo,
    correo_simulado,
    monkeypatch,
):

    preparar_registros(
        cupo,
        total=20,
        minutos=1,
    )

    def prohibido(*args):

        pytest.fail(
            "No debe buscar usuarios "
            "cuando el limite esta agotado."
        )

    monkeypatch.setattr(
        servicio,

        "buscar_usuario_por_email",

        prohibido,
    )

    a = solicitar(
        client,
        "qa.primero@example.com",
    )

    b = solicitar(
        client,
        "qa.segundo@example.com",
    )

    assert a.status_code == 429

    assert b.status_code == 429

    assert a.json() == b.json()

    assert not correo_simulado


# ======================================
# 5. RECUPERACION DESHABILITADA
# ======================================

def test_deshabilitada_no_consume_cupo(
    client,
    cupo,
    monkeypatch,
):

    monkeypatch.setenv(
        "RECUPERACION_HABILITADA",
        "0",
    )

    respuesta = solicitar(client)

    assert respuesta.status_code == 503

    assert cantidad(cupo) == 0