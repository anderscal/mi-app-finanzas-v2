
"""Auditoria integral del asistente financiero.

Paso 27.8.

Incluye:
- Autenticacion y aislamiento.
- Consentimiento efectivo.
- Consultas SQL y SPARQL redundantes.
- Volumen de obligaciones.
- Caida de Fuseki.
- Pertinencia de consultas especificas.
- Periodos no soportados.
- Respuestas invalidas del proveedor.

Usar exclusivamente la base de datos de pruebas.
"""

import json

from collections import Counter

from decimal import Decimal

from types import SimpleNamespace

import pytest

from sqlalchemy import event

from app.business import (
    rag_presentacion_pertinente as presentacion,
)

from app.routers import rag_router

from app.schemas.rag_schema import (
    PreguntaConIA,
)

from app.services import (
    rag_ia_service as gateway,
)

from app.services.fuseki_client import (
    FusekiNoDisponible,
)

from app.tests.helpers import (
    crear_cuenta,
    crear_usuario_autenticado,
)

from app.tests.test_rag_271 import (
    simular_fuseki,
)

from app.tests.test_rag_277 import (
    contexto_prueba,
)


RUTA = "/consultas/asistente"

PREGUNTA_SALDO = (
    "¿Cuánto dinero tengo disponible?"
)


def no_llamar(*args, **kwargs):

    raise AssertionError(
        "Se ejecuto una operacion no autorizada "
        "o innecesaria."
    )


def desactivar_sync_real(monkeypatch):
    """Las pruebas no deben publicar grafos reales."""

    monkeypatch.setattr(
        rag_router,
        "asegurar_actualizacion_para_rag",
        lambda *args, **kwargs: None,
    )


def configurar_ia_simulada(monkeypatch):

    monkeypatch.setenv(
        "RAG_IA_HABILITADA",
        "1",
    )

    monkeypatch.setenv(
        "GEMINI_API_KEY",
        "clave-simulada-auditoria",
    )

    monkeypatch.setenv(
        "GEMINI_RAG_MODEL",
        "gemini-3.5-flash-lite",
    )


# =======================================
# SEGURIDAD
# =======================================

def test_278_token_invalido_rechazado(
    client,
    monkeypatch,
):

    monkeypatch.setattr(
        rag_router,
        "_recuperar",
        no_llamar,
    )

    respuesta = client.post(
        f"{RUTA}/contexto",

        headers={
            "Authorization": (
                "Bearer token-invalido"
            )
        },

        json={
            "pregunta": PREGUNTA_SALDO,
        },
    )

    assert respuesta.status_code in {
        401,
        403,
    }


def test_278_sin_consentimiento_no_recupera_ni_envia(
    monkeypatch,
):

    configurar_ia_simulada(
        monkeypatch
    )

    monkeypatch.setattr(
        rag_router,
        "_recuperar",
        no_llamar,
    )

    monkeypatch.setattr(
        rag_router,
        "generar_respuesta_rag",
        no_llamar,
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:

        rag_router.responder_con_rag(
            PreguntaConIA(
                pregunta=PREGUNTA_SALDO,
                autorizo_envio_ia=False,
            ),

            db=object(),

            usuario=SimpleNamespace(
                id_usuario=7
            ),
        )

    assert error.value.status_code == 403


def test_278_no_permite_elegir_otro_usuario(
    client,
    db_session,
    monkeypatch,
):

    desactivar_sync_real(
        monkeypatch
    )

    usuario_a, headers_a = (
        crear_usuario_autenticado(
            client,
            db_session,
            "qa.278.a@example.com",
        )
    )

    usuario_b, _ = (
        crear_usuario_autenticado(
            client,
            db_session,
            "qa.278.b@example.com",
        )
    )

    crear_cuenta(
        db_session,
        usuario_a.id_usuario,
        "Cuenta auditoria A",
        "100000.00",
    )

    crear_cuenta(
        db_session,
        usuario_b.id_usuario,
        "Cuenta auditoria B privada",
        "999999.00",
    )

    consultas = simular_fuseki(
        monkeypatch
    )

    respuesta = client.post(
        f"{RUTA}/contexto",

        headers=headers_a,

        json={
            "pregunta": PREGUNTA_SALDO,

            # Intento de sustituir el usuario
            # autenticado mediante el cuerpo HTTP.
            "id_usuario": usuario_b.id_usuario,
        },
    )

    # Es valido rechazar propiedades adicionales.
    if respuesta.status_code == 422:

        assert consultas == []

        return

    assert respuesta.status_code == 200

    contexto = respuesta.json()

    nombres = [
        fila["nombre"]

        for fila in contexto[
            "postgresql"
        ]["cuentas"]
    ]

    assert nombres == [
        "Cuenta auditoria A"
    ]

    assert (
        "Cuenta auditoria B privada"
        not in respuesta.text
    )

    assert contexto["fuseki"]["grafo"] == (
        "urn:finanzas:grafo:usuario:"
        f"{usuario_a.id_usuario}"
    )

    assert not any(
        (
            "GRAPH <urn:finanzas:grafo:usuario:"
            f"{usuario_b.id_usuario}>"
        ) in consulta

        for consulta in consultas
    )


# =======================================
# EFICIENCIA DE RECUPERACION
# =======================================

def test_278_respaldo_no_repite_consultas(
    client,
    db_session,
    monkeypatch,
):

    configurar_ia_simulada(
        monkeypatch
    )

    desactivar_sync_real(
        monkeypatch
    )

    usuario, headers = (
        crear_usuario_autenticado(
            client,
            db_session,
            "qa.278.eficiencia@example.com",
        )
    )

    crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta auditoria rendimiento",
        "75000.00",
    )

    consultas_rdf = simular_fuseki(
        monkeypatch
    )

    def gemini_no_disponible(*args, **kwargs):

        raise gateway.IANoDisponible(
            "Fallo temporal simulado",
            codigo_http=503,
            transitorio=True,
        )

    monkeypatch.setattr(
        rag_router,
        "generar_respuesta_rag",
        gemini_no_disponible,
    )

    sentencias = Counter()

    def registrar_sql(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):

        # Solo contabiliza operaciones.
        # No registra SQL ni parametros privados.
        sentencias["total"] += 1

    bind = db_session.get_bind()

    event.listen(
        bind,
        "before_cursor_execute",
        registrar_sql,
    )

    try:

        respuesta_contexto = client.post(
            f"{RUTA}/contexto",

            headers=headers,

            json={
                "pregunta": PREGUNTA_SALDO,
            },
        )

        assert respuesta_contexto.status_code == 200

        sql_contexto = sentencias["total"]

        rdf_contexto = len(consultas_rdf)

        sentencias.clear()
        consultas_rdf.clear()

        respuesta_respaldo = client.post(
            f"{RUTA}/preguntar",

            headers=headers,

            json={
                "pregunta": PREGUNTA_SALDO,
                "autorizo_envio_ia": True,
            },
        )

        sql_respaldo = sentencias["total"]

        rdf_respaldo = len(consultas_rdf)

    finally:

        event.remove(
            bind,
            "before_cursor_execute",
            registrar_sql,
        )

    assert respuesta_respaldo.status_code == 200

    datos = respuesta_respaldo.json()

    assert datos["metodo"] == (
        "CALCULO_SQL_RESPALDO"
    )

    assert "$75.000 COP" in datos["respuesta"]

    assert sql_contexto > 0

    assert sql_respaldo <= sql_contexto

    assert rdf_contexto == 1
    assert rdf_respaldo == 1

    print(
        "\nConsultas auditoria:"
        f"\nSQL contexto: {sql_contexto}"
        f"\nSQL respaldo: {sql_respaldo}"
        f"\nSPARQL contexto: {rdf_contexto}"
        f"\nSPARQL respaldo: {rdf_respaldo}"
    )


# =======================================
# VOLUMEN Y EXACTITUD
# =======================================

def contexto_con_obligaciones(cantidad):

    contexto = contexto_prueba()

    contexto["postgresql"][
        "obligaciones"
    ] = [
        {
            "id_obligacion": indice,

            "nombre": (
                f"Cobro auditoria {indice}"
            ),

            "tipo": "POR_COBRAR",

            "estado": "ACTIVA",

            "pendiente": "100.00",
        }

        for indice in range(
            1,
            cantidad + 1,
        )
    ]

    total = (
        Decimal("100.00")
        * cantidad
    )

    contexto["analisis_financiero"][
        "obligaciones"
    ] = {
        "obligaciones_totales": cantidad,

        "deudas_propias_activas": 0,
        "deudas_propias_saldadas": 0,

        "cobros_activos": cantidad,
        "cobros_saldados": 0,

        "monto_pendiente_por_pagar": "0.00",

        "monto_pendiente_por_cobrar": str(
            total
        ),
    }

    return contexto


@pytest.mark.parametrize(
    "cantidad, esperado",
    [
        (1000, "$100.000 COP"),
        (10000, "$1.000.000 COP"),
    ],
)
def test_278_totales_grandes_sin_truncamiento(
    cantidad,
    esperado,
):

    respuesta = (
        presentacion.generar_respuesta_local_pertinente(
            "¿Cuánto dinero me deben?",

            contexto_con_obligaciones(
                cantidad
            ),
        )
    )

    assert esperado in respuesta

    assert "Cobro auditoria" not in respuesta

    # La longitud no debe crecer junto
    # con el numero de obligaciones.
    assert len(respuesta) < 1000


def test_278_listado_grande_informa_limite():

    respuesta = (
        presentacion.generar_respuesta_local_pertinente(
            "¿Quiénes me deben dinero?",

            contexto_con_obligaciones(
                1000
            ),
        )
    )

    assert "$100.000 COP" in respuesta

    assert "20 de 1000 registros" in respuesta

    assert respuesta.count(
        "Cobro auditoria "
    ) == 20


# =======================================
# RESILIENCIA
# =======================================

def test_278_fuseki_caido_no_inventa_contexto(
    monkeypatch,
):

    configurar_ia_simulada(
        monkeypatch
    )

    desactivar_sync_real(
        monkeypatch
    )

    from fastapi import HTTPException

    def fuseki_caido(*args, **kwargs):

        raise FusekiNoDisponible(
            "Caida simulada"
        )

    monkeypatch.setattr(
        rag_router,
        "construir_contexto_rag",
        fuseki_caido,
    )

    monkeypatch.setattr(
        rag_router,
        "generar_respuesta_rag",
        no_llamar,
    )

    with pytest.raises(HTTPException) as error:

        rag_router.responder_con_rag(
            PreguntaConIA(
                pregunta=PREGUNTA_SALDO,

                autorizo_envio_ia=True,
            ),

            db=object(),

            usuario=SimpleNamespace(
                id_usuario=7
            ),
        )

    assert error.value.status_code == 503

    assert "Fuseki" in str(
        error.value.detail
    )


def test_278_gemini_respuesta_malformada_controlada(
    monkeypatch,
):

    configurar_ia_simulada(
        monkeypatch
    )

    class RespuestaMalformada:

        def __enter__(self):

            return self

        def __exit__(self, *args):

            return False

        def read(self):

            return json.dumps({
                "candidates": [{
                    "finishReason": "STOP",

                    "content": {
                        "parts": None,
                    },
                }],
            }).encode("utf-8")

    monkeypatch.setattr(
        gateway,
        "urlopen",

        lambda *args, **kwargs: (
            RespuestaMalformada()
        ),
    )

    # Un JSON inesperado del proveedor debe
    # producir un error controlado de IA,
    # nunca un TypeError sin gestionar.

    with pytest.raises(
        gateway.IANoDisponible
    ):

        gateway.generar_respuesta_gemini(
            "Organiza la evidencia",
            {},
            "Responde en JSON",
        )


# =======================================
# COBERTURA Y LIMITACIONES EXPLICITAS
# =======================================

def test_278_periodo_historico_no_se_sustituye(
    client,
    db_session,
    monkeypatch,
):

    desactivar_sync_real(
        monkeypatch
    )

    _, headers = crear_usuario_autenticado(
        client,

        db_session,

        "qa.278.periodos@example.com",
    )

    simular_fuseki(
        monkeypatch
    )

    respuesta = client.post(
        f"{RUTA}/contexto",

        headers=headers,

        json={
            "pregunta": (
                "¿Cuánto gasté en enero de 2025?"
            ),
        },
    )

    # No exigimos implementar periodos
    # arbitrarios para aprobar la prueba.
    #
    # Se admite un rechazo explicito cuando
    # el periodo no esta soportado.

    if respuesta.status_code == 422:

        detalle = str(
            respuesta.json().get("detail", "")
        ).lower()

        assert (
            "período" in detalle
            or "periodo" in detalle
            or "mes" in detalle
            or "fecha" in detalle
        )

        return

    assert respuesta.status_code == 200

    periodo = respuesta.json()[
        "periodo"
    ]

    assert (
        periodo["anio"],
        periodo["mes"],
    ) == (
        2025,
        1,
    ), (
        "El periodo solicitado fue sustituido "
        "silenciosamente por otro."
    )


def _limitacion_explicita(texto):

    texto = texto.lower()

    return any(
        expresion in texto

        for expresion in (
            "no puedo filtrar",
            "no se admite",
            "no está soportad",
            "no está disponible el filtro",
            "no se admite ese filtro",
            "no puedo determinar",
            "no puedo identificar",
            "no es posible determinar",
            "no se recuperó evidencia suficiente",
        )
    )


def test_278_categoria_especifica_no_devuelve_total_general():

    contexto = contexto_prueba()

    contexto["postgresql"][
        "gastos_por_categoria"
    ].append({
        "categoria": "Transporte",

        "total_incluido_gmf": "22420.00",
    })

    respuesta = (
        presentacion.generar_respuesta_local_pertinente(
            "¿Cuánto gasté en Transporte este mes?",

            contexto,
        )
    )

    respuesta_especifica = (
        "Transporte" in respuesta

        and "$22.420 COP" in respuesta
    )

    assert (
        respuesta_especifica
        or _limitacion_explicita(respuesta)
    ), (
        "No se aplico ni se advirtio "
        "la ausencia del filtro por categoria."
    )


def test_278_cuenta_especifica_no_devuelve_saldo_global():

    contexto = contexto_prueba()

    contexto["postgresql"][
        "cuentas"
    ].append({
        "id_cuenta": 902,

        "nombre": "Segunda cuenta auditoria",

        "tipo": "AHORROS",

        "saldo_real": "200000.00",

        "reservado": "0.00",

        "saldo_libre": "200000.00",
    })

    contexto["analisis_financiero"][
        "cuentas"
    ] = {
        "numero_cuentas_activas": 2,

        "saldo_real_total": "1200000.00",

        "reservado_total": "350000.00",

        "saldo_libre_total": "850000.00",
    }

    respuesta = (
        presentacion.generar_respuesta_local_pertinente(
            "¿Cuánto dinero tengo disponible "
            "en Caja privada?",

            contexto,
        )
    )

    respuesta_especifica = (
        "Caja privada" in respuesta

        and "$650.000 COP" in respuesta
    )

    assert (
        respuesta_especifica
        or _limitacion_explicita(respuesta)
    ), (
        "Se devolvio el saldo global sin "
        "advertir que no se aplico el filtro "
        "de cuenta solicitado."
    )
