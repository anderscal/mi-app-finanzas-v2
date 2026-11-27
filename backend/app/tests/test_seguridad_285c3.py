import pytest

from sqlalchemy import text

from app.business import (
    seguridad_productiva_service as seguridad,
)


EMAIL = "qa.seguridad285c3@example.com"

PASSWORD = "PasswordPrueba2026!"

REGISTRO = {
    "nombre_1": "Prueba",
    "apellido_1": "Seguridad",
    "email": EMAIL,
    "password": PASSWORD,
}

RUTA_RAG = "/consultas/asistente/preguntar"


@pytest.fixture(autouse=True)
def limpiar_cupos(db_session):

    db_session.execute(
        text("DELETE FROM public.limite_operacion")
    )

    db_session.commit()


def cantidad(db, operacion):

    return db.scalar(
        text("""
            SELECT COUNT(*)
            FROM public.limite_operacion
            WHERE operacion = :operacion
        """),
        {
            "operacion": operacion
        },
    )


def preparar(db, operacion, total, minutos, sujeto=None):

    db.execute(
        text("""
            INSERT INTO public.limite_operacion
                (operacion, sujeto, fecha)

            SELECT
                :operacion,
                :sujeto,
                clock_timestamp()
                    - make_interval(mins => :minutos)

            FROM generate_series(1, :total)
        """),
        {
            "operacion": operacion,
            "sujeto": sujeto or ("a" * 64),
            "minutos": minutos,
            "total": total,
        },
    )

    db.commit()


def login(client, email=EMAIL, password=PASSWORD):

    return client.post(
        "/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )


@pytest.fixture
def cuenta_demo(client, monkeypatch):

    r = client.post(
        "/auth/registro",
        json=REGISTRO,
    )

    assert r.status_code == 201, r.text

    uid = r.json()["id_usuario"]

    r = login(client)

    assert r.status_code == 200, r.text

    headers = {
        "Authorization":
            "Bearer " + r.json()["access_token"]
    }

    monkeypatch.setenv(
        "RAG_IA_HABILITADA",
        "1",
    )

  

    return uid, headers


@pytest.fixture
def ia_simulada(monkeypatch):

    llamadas = []

    def responder(db, uid, pregunta, autorizo):

        llamadas.append(uid)

        return {
            "respuesta": "Respuesta ficticia QA"
        }

    monkeypatch.setattr(
        seguridad,
        "responder_asistente",
        responder,
    )

    return llamadas


def preguntar(client, headers, autorizo=True):

    return client.post(
        RUTA_RAG,
        headers=headers,
        json={
            "pregunta": "Cuanto dinero tengo disponible",
            "autorizo_envio_ia": autorizo,
        },
    )


# ======================================
# 1. LIMITE INDIVIDUAL DE LOGIN
# ======================================

def test_login_limite_individual(
    client,
    db_session,
):

    for _ in range(8):

        r = login(client)

        assert r.status_code == 401

    r = login(
        client,
        email=EMAIL.upper(),
    )

    assert r.status_code == 429

    assert cantidad(
        db_session,
        "login",
    ) == 8


# ======================================
# 2. LIMITE GLOBAL DE LOGIN
# ======================================

def test_login_limite_global(
    client,
    db_session,
):

    preparar(
        db_session,
        "login",
        60,
        1,
    )

    assert login(
        client
    ).status_code == 429


# ======================================
# 3. LIMITE GLOBAL DE REGISTRO
# ======================================

def test_registro_limite_global(
    client,
    db_session,
):

    preparar(
        db_session,
        "registro",
        15,
        1,
    )

    r = client.post(
        "/auth/registro",
        json=REGISTRO,
    )

    assert r.status_code == 429

    assert cantidad(
        db_session,
        "registro",
    ) == 15


# ======================================
# 4-5. RECHAZOS PREVIOS AL RAG
# ======================================

@pytest.mark.parametrize(
    "habilitada, consentimiento, esperado",
    [
        ("1", False, 403),
        ("0", True, 503),
    ],
)
def test_rechazo_rag(
    client,
    db_session,
    cuenta_demo,
    ia_simulada,
    monkeypatch,
    habilitada,
    consentimiento,
    esperado,
):

    uid, headers = cuenta_demo

    monkeypatch.setenv(
        "RAG_IA_HABILITADA",
        habilitada,
    )

    r = preguntar(
        client,
        headers,
        consentimiento,
    )

    assert r.status_code == esperado

    assert not ia_simulada

    assert cantidad(
        db_session,
        "rag",
    ) == 0


# ======================================
# 6. ACCESO SIN LISTA DE USUARIOS
# ======================================

def test_rag_usuario_autenticado(
    client,
    db_session,
    cuenta_demo,
    ia_simulada,
    monkeypatch,
):

    uid, headers = cuenta_demo

    monkeypatch.delenv(
        "RAG_DEMO_USUARIOS",
        raising=False,
    )

    r = preguntar(
        client,
        headers,
        True,
    )

    assert r.status_code == 200

    assert ia_simulada == [uid]

    assert cantidad(
        db_session,
        "rag",
    ) == 1


# ======================================
# 7. LIMITE RAG INDIVIDUAL
# ======================================

def test_rag_limite_individual(
    client,
    db_session,
    cuenta_demo,
    ia_simulada,
):

    uid, headers = cuenta_demo

    for _ in range(10):

        r = preguntar(
            client,
            headers,
        )

        assert r.status_code == 200

    assert preguntar(
        client,
        headers,
    ).status_code == 429

    assert ia_simulada == [uid] * 10

    assert cantidad(
        db_session,
        "rag",
    ) == 10


# ======================================
# 8. LIMITE RAG GLOBAL DIARIO
# ======================================

def test_rag_limite_global(
    client,
    db_session,
    cuenta_demo,
    ia_simulada,
):

    _, headers = cuenta_demo

    preparar(
        db_session,
        "rag",
        100,
        60,
    )

    assert preguntar(
        client,
        headers,
    ).status_code == 429

    assert not ia_simulada


# ======================================
# 9. LIMITE RAG INDIVIDUAL DIARIO
# ======================================

def test_rag_limite_individual_diario(
    client,
    db_session,
    cuenta_demo,
    ia_simulada,
):

    uid, headers = cuenta_demo

    preparar(
        db_session,
        "rag",
        30,
        60,
        sujeto=seguridad._huella(
            "rag",
            str(uid),
        ),
    )

    assert preguntar(
        client,
        headers,
    ).status_code == 429

    assert not ia_simulada


# ======================================
# 10. LIBERACION DE CUPOS EXPIRADOS
# ======================================

def test_cupos_expirados(
    client,
    db_session,
):

    preparar(
        db_session,
        "login",
        500,
        1500,
    )

    assert login(
        client
    ).status_code == 401

    assert cantidad(
        db_session,
        "login",
    ) == 1