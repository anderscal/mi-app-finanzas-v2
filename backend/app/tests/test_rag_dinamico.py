"""Pruebas del RAG dinámico 27.9 A.

Las pruebas de PostgreSQL utilizan las fixtures
existentes del proyecto.

No realizan llamadas reales a Google Gemini.
"""

import json

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from pydantic import ValidationError

from rdflib import Dataset, Literal, RDF, URIRef

from sqlalchemy.dialects import postgresql

from app.business.rag_contrato import (
    Consulta,
    PlanConsulta,
    declaracion_herramienta,
    preparar_consulta,
)

from app.business.rag_contexto_ia import (
    RegistroAlias,
    proteger_evidencia,
)

from app.business import rag_service

from app.business import (
    rag_retrieval_service as retrieval,
)

from app.business.planificacion_service import (
    consultar_planificacion,
)

from app.models import (
    AporteMeta,
    MetaFinanciera,
    Movimiento,
    ObligacionFinanciera,
    Presupuesto,
)

from app.persistence.cuenta_repository import (
    obtener_cuentas_con_saldo,
)

from app.persistence.movimiento_repository import (
    obtener_totales_mes,
)

from app.persistence.rag_consulta_repository import (
    construir_select,
    ejecutar_consulta_sql,
)

from app.persistence.rag_semantico_consulta_repository import (
    construir_sparql,
    ejecutar_consulta_rdf,
)

from app.persistence.rag_semantico_repository import (
    FIN,
    OP,
)

from app.services import rag_ia_service as gateway

from app.tests.helpers import (
    crear_cuenta,
    crear_usuario_autenticado,
    obtener_categoria_sistema,
)


RUTA = "/consultas/asistente"


def consulta_sql(
    db,
    usuario,
    **argumentos,
):

    consulta = Consulta(**argumentos)

    plan = preparar_consulta(
        consulta,
        lambda valor: valor,
    )

    return ejecutar_consulta_sql(
        db,
        usuario,
        plan,
    )


def no_llamar(*args, **kwargs):

    raise AssertionError(
        "Se ejecutó una operación prohibida."
    )


# ======================================
# CONTRATO Y VALIDACION
# ======================================

@pytest.mark.parametrize(
    "cambios",
    [
        {"id_usuario": 999},

        {"entidad": "usuario"},

        {"operacion": "eliminar"},

        {"campos": ["password"]},

        {"limite": 5000},

        {
            "filtros": [{
                "campo": "id_usuario",
                "operador": "igual",
                "valor": "2",
            }],
        },

        {"orden_campo": "DROP TABLE movimiento"},

        {
            "entidad": "rdf_reservas",
            "operacion": "sumar",
            "campo": "monto",
        },

        {
            "entidad": "movimientos",
            "campos": ["fecha"],
            "filtros": [{
                "campo": "fecha",
                "operador": "mayor",
                "valor": "2026-99-99",
            }],
        },

        {
            "filtros": [{
                "campo": "saldo_real",
                "operador": "mayor",
                "valor": "NaN",
            }],
        },
    ],
)
def test_279_contrato_rechaza_operaciones_invalidas(
    cambios,
):

    argumentos = {
        "entidad": "cuentas",
        "operacion": "listar",
        "campos": ["nombre"],
        **cambios,
    }

    with pytest.raises(ValidationError):

        Consulta.model_validate(
            argumentos
        )


def test_279_rechaza_plan_excesivo():

    with pytest.raises(ValidationError):

        PlanConsulta.model_validate({
            "estado": "consultar",

            "consultas": [
                {
                    "entidad": "cuentas",
                    "operacion": "contar",
                }

                for _ in range(7)
            ],
        })


def test_279_sql_utiliza_parametros():

    texto = "Caja'; DROP TABLE usuario; --"

    consulta = Consulta(
        entidad="cuentas",

        operacion="listar",

        campos=["nombre"],

        filtros=[{
            "campo": "nombre",
            "operador": "igual",
            "valor": texto,
        }],
    )

    sentencia = construir_select(
        7,

        preparar_consulta(
            consulta,
            lambda valor: valor,
        ),
    )

    compilado = sentencia.compile(
        dialect=postgresql.dialect()
    )

    assert texto not in str(compilado)

    assert any(
        valor == texto.lower()

        for valor in compilado.params.values()
    )

    assert sentencia.is_select


# ======================================
# AISLAMIENTO Y CONSULTAS REUTILIZABLES
# ======================================

def test_279_cuentas_filtros_aislamiento(
    client,
    db_session,
):

    usuario_a, _ = (
        crear_usuario_autenticado(
            client,
            db_session,
            "qa.279.cuentas.a@example.com",
        )
    )

    usuario_b, _ = (
        crear_usuario_autenticado(
            client,
            db_session,
            "qa.279.cuentas.b@example.com",
        )
    )

    crear_cuenta(
        db_session,
        usuario_a.id_usuario,
        "Caja A",
        "100000.00",
    )

    crear_cuenta(
        db_session,
        usuario_a.id_usuario,
        "Caja vacia A",
        "0.00",
    )

    crear_cuenta(
        db_session,
        usuario_b.id_usuario,
        "Caja B privada",
        "999999.00",
    )

    resultado = consulta_sql(
        db_session,

        usuario_a.id_usuario,

        entidad="cuentas",

        operacion="sumar",

        campo="saldo_real",
    )

    assert (
        resultado["filas"][0]["valor"]
        == Decimal("100000.00")
    )

    conteo = consulta_sql(
        db_session,

        usuario_a.id_usuario,

        entidad="cuentas",

        operacion="contar",

        filtros=[{
            "campo": "saldo_real",
            "operador": "igual",
            "valor": "0",
        }],
    )

    assert conteo["filas"][0]["valor"] == 1

    listado = consulta_sql(
        db_session,

        usuario_a.id_usuario,

        entidad="cuentas",

        operacion="listar",

        campos=[
            "nombre",
            "saldo_real",
        ],

        orden_campo="saldo_real",

        descendente=True,
    )

    assert [
        fila["nombre"]

        for fila in listado["filas"]

    ] == [
        "Caja A",
        "Caja vacia A",
    ]


def crear_movimiento_prueba(
    cuenta,
    categoria,
    monto,
    fecha,
    gmf="0.00",
    origen="NORMAL",
    tipo="GASTO",
    obligacion=None,
):

    return Movimiento(
        uuid_local=uuid4(),

        id_cuenta=cuenta.id_cuenta,

        id_categoria=(
            categoria.id_categoria
            if categoria is not None
            else None
        ),

        id_obligacion=(
            obligacion.id_obligacion
            if obligacion is not None
            else None
        ),

        tipo=tipo,

        origen=origen,

        monto=Decimal(monto),

        fecha_movimiento=fecha,

        aplica_gmf=Decimal(gmf) > 0,

        monto_gmf=Decimal(gmf),

        estado="ACTIVO",
    )


def test_279_agregados_no_se_truncan(
    client,
    db_session,
):

    usuario, _ = crear_usuario_autenticado(
        client,

        db_session,

        "qa.279.volumen@example.com",
    )

    cuenta = crear_cuenta(
        db_session,

        usuario.id_usuario,

        "Cuenta volumen",

        "1000000.00",
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO",
    )

    movimientos = [
        crear_movimiento_prueba(
            cuenta,

            categoria,

            "100.00",

            date(2026, 11, 1),
        )

        for _ in range(60)
    ]

    db_session.add_all(movimientos)
    db_session.flush()

    resultado = consulta_sql(
        db_session,

        usuario.id_usuario,

        entidad="movimientos",

        operacion="sumar",

        campo="monto",

        limite=1,
    )

    assert (
        resultado["filas"][0]["valor"]
        == Decimal("6000.00")
    )

    assert resultado["filas"][0]["cantidad"] == 60

    listado = consulta_sql(
        db_session,

        usuario.id_usuario,

        entidad="movimientos",

        operacion="listar",

        campos=["fecha", "monto"],

        orden_campo="fecha",

        descendente=True,

        limite=5,
    )

    assert len(listado["filas"]) == 5
    assert listado["truncado"] is True


# ======================================
# EQUIVALENCIA CONTABLE
# ======================================

def test_279_equivalencia_con_reglas_financieras(
    client,
    db_session,
):

    usuario, _ = crear_usuario_autenticado(
        client,

        db_session,

        "qa.279.equivalencia@example.com",
    )

    uid = usuario.id_usuario

    cuenta = crear_cuenta(
        db_session,

        uid,

        "Cuenta equivalencia",

        "1000000.00",
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO",
    )

    meta = MetaFinanciera(
        id_usuario=uid,

        nombre_meta="Meta equivalencia",

        monto_objetivo=Decimal("100000.00"),

        monto_acumulado=Decimal("20000.00"),

        fecha_objetivo=date(2027, 12, 31),

        estado="ACTIVA",
    )

    presupuesto = Presupuesto(
        id_usuario=uid,

        id_categoria=categoria.id_categoria,

        anio=2026,

        mes=11,

        monto_limite=Decimal("80000.00"),
    )

    obligacion = ObligacionFinanciera(
        id_usuario=uid,

        nombre_obligacion="Deuda equivalencia",

        tipo_obligacion="POR_PAGAR",

        monto_original=Decimal("50000.00"),

        fecha_inicio=date(2026, 11, 1),

        estado="ACTIVA",
    )

    db_session.add_all([
        meta,
        presupuesto,
        obligacion,
    ])

    db_session.flush()

    db_session.add(
        AporteMeta(
            uuid_operacion=uuid4(),

            id_usuario=uid,

            id_meta=meta.id_meta,

            id_cuenta=cuenta.id_cuenta,

            tipo="RESERVA",

            monto=Decimal("20000.00"),

            fecha_operacion=date(
                2026, 11, 1
            ),

            estado="ACTIVO",
        )
    )

    db_session.add_all([
        crear_movimiento_prueba(
            cuenta,

            categoria,

            "20000.00",

            date(2026, 11, 2),

            gmf="80.00",
        ),

        crear_movimiento_prueba(
            cuenta,

            None,

            "10000.00",

            date(2026, 11, 3),

            origen="OBLIGACION",

            obligacion=obligacion,
        ),
    ])

    db_session.flush()

    cuentas_originales = (
        obtener_cuentas_con_saldo(
            db_session,
            uid,
        )
    )

    cuentas = consulta_sql(
        db_session,

        uid,

        entidad="cuentas",

        operacion="listar",

        campos=[
            "saldo_real",
            "reservado",
            "saldo_libre",
        ],
    )["filas"]

    assert (
        cuentas[0]["saldo_real"]
        == cuentas_originales[0]["saldo_actual"]
    )

    assert (
        cuentas[0]["reservado"]
        == Decimal("20000.00")
    )

    assert (
        cuentas[0]["saldo_real"]
        - cuentas[0]["reservado"]
        == cuentas[0]["saldo_libre"]
    )

    planificacion = consultar_planificacion(
        db_session,
        uid,
    )

    metas = consulta_sql(
        db_session,

        uid,

        entidad="metas",

        operacion="listar",

        campos=["progreso"],
    )["filas"]

    assert (
        metas[0]["progreso"]

        == planificacion["metas"][0][
            "porcentaje_progreso"
        ]
    )

    obligaciones = consulta_sql(
        db_session,

        uid,

        entidad="obligaciones",

        operacion="listar",

        campos=["pendiente"],
    )["filas"]

    assert (
        obligaciones[0]["pendiente"]

        == planificacion["obligaciones"][0][
            "monto_pendiente"
        ]

        == Decimal("40000.00")
    )

    presupuestos = consulta_sql(
        db_session,

        uid,

        entidad="presupuestos",

        operacion="listar",

        campos=[
            "gastado",
            "disponible",
            "porcentaje_usado",
        ],
    )["filas"]

    original = planificacion[
        "presupuestos"
    ][0]

    for campo in (
        "gastado",
        "disponible",
        "porcentaje_usado",
    ):

        assert (
            presupuestos[0][campo]
            == original[campo]
        )

    totales = obtener_totales_mes(
        db_session,

        uid,

        date(2026, 11, 1),

        date(2026, 12, 1),
    )

    nuevo_gmf = consulta_sql(
        db_session,

        uid,

        entidad="movimientos",

        operacion="sumar",

        campo="gmf",

        filtros=[
            {
                "campo": "fecha",
                "operador": "mayor_igual",
                "valor": "2026-11-01",
            },
            {
                "campo": "fecha",
                "operador": "menor",
                "valor": "2026-12-01",
            },
            {
                "campo": "estado",
                "operador": "igual",
                "valor": "ACTIVO",
            },
        ],
    )

    assert (
        nuevo_gmf["filas"][0]["valor"]
        == totales["gmf"]
    )


# ======================================
# SPARQL REAL SOBRE RDF DE PRUEBA
# ======================================

def test_279_relacion_semantica_y_aislamiento():

    dataset = Dataset()

    def agregar_reserva(
        usuario,
        nombre_meta,
        nombre_cuenta,
    ):

        grafo = dataset.graph(
            URIRef(
                f"urn:finanzas:grafo:usuario:{usuario}"
            )
        )

        evento = URIRef(
            f"https://prueba.local/{usuario}/evento/1"
        )

        meta = URIRef(
            f"https://prueba.local/{usuario}/meta/1"
        )

        cuenta = URIRef(
            f"https://prueba.local/{usuario}/cuenta/1"
        )

        grafo.add((
            evento,
            RDF.type,
            FIN.ReservaMeta,
        ))

        grafo.add((
            evento,
            FIN.correspondeAMeta,
            meta,
        ))

        grafo.add((
            evento,
            FIN.seRealizaDesdeCuenta,
            cuenta,
        ))

        grafo.add((
            evento,
            FIN.tieneFechaOperacion,
            Literal(date(2026, 11, 1)),
        ))

        grafo.add((
            evento,
            FIN.tieneEstadoAporte,
            Literal("ACTIVO"),
        ))

        grafo.add((
            meta,
            FIN.tieneNombreMeta,
            Literal(nombre_meta),
        ))

        grafo.add((
            cuenta,
            FIN.tieneNombreCuenta,
            Literal(nombre_cuenta),
        ))

    agregar_reserva(
        7,
        "Meta A",
        "Cuenta A",
    )

    agregar_reserva(
        8,
        "Meta B privada",
        "Cuenta B privada",
    )

    def ejecutar(sparql):

        respuesta = dataset.query(sparql)

        datos = json.loads(
            respuesta.serialize(
                format="json"
            )
        )

        return datos["results"]["bindings"]

    consulta = Consulta(
        entidad="rdf_reservas",

        operacion="listar",

        campos=[
            "meta",
            "cuenta",
            "tipo",
        ],

        filtros=[{
            "campo": "estado",
            "operador": "igual",
            "valor": "ACTIVO",
        }],
    )

    plan = preparar_consulta(
        consulta,
        lambda valor: valor,
    )

    resultado = ejecutar_consulta_rdf(
        7,

        plan,

        ejecutar,
    )

    assert resultado["filas"] == [{
        "meta": "Meta A",
        "cuenta": "Cuenta A",
        "tipo": "RESERVA",
    }]


def test_279_sparql_rechaza_grafo_externo():

    consulta = Consulta(
        entidad="rdf_categorias",

        operacion="contar",
    )

    plan = preparar_consulta(
        consulta,
        lambda valor: valor,
    )

    with pytest.raises(ValueError):

        construir_sparql(
            "7> } UNION { GRAPH ?g {",

            plan,
        )


# ======================================
# PRIVACIDAD
# ======================================

def test_279_alias_de_pregunta_y_evidencia():

    registro = RegistroAlias([
        "Caja familiar privada",
        "Meta privada",
    ])

    pregunta = registro.proteger(
        "¿Cuánto tengo en Caja familiar privada?"
    )

    assert "Caja familiar privada" not in pregunta

    evidencia = proteger_evidencia(
        [{
            "origen": "PostgreSQL",

            "filas": [{
                "nombre": "Caja familiar privada",

                "saldo_real": Decimal("50000.00"),
            }],

            "filtros": [{
                "campo": "nombre",

                "operador": "igual",

                "valor": "Caja familiar privada",
            }],
        }],

        registro,
    )

    enviado = json.dumps(
        evidencia,
        ensure_ascii=False,
    )

    assert "Caja familiar privada" not in enviado

    assert "50000.00" in enviado

    assert (
        "Caja familiar privada"
        in registro.restaurar(pregunta)
    )


# ======================================
# PROTOCOLO GEMINI
# ======================================

def test_279_function_call_y_function_response(
    monkeypatch,
):

    enviados = []

    herramienta = declaracion_herramienta()

    def enviar(
        cuerpo,
        modelo,
        limite,
    ):

        enviados.append(cuerpo)

        if len(enviados) == 1:

            return {
                "candidates": [{
                    "finishReason": "STOP",

                    "content": {
                        "role": "model",

                        "parts": [{
                            "thoughtSignature": (
                                "firma-simulada"
                            ),

                            "functionCall": {
                                "name": herramienta["name"],

                                "args": {
                                    "estado": "consultar",

                                    "consultas": [{
                                        "entidad": "cuentas",

                                        "operacion": "contar",
                                    }],
                                },
                            },
                        }],
                    },
                }],
            }

        return {
            "candidates": [{
                "finishReason": "STOP",

                "content": {
                    "parts": [{
                        "text": (
                            "Tienes 2 cuentas. [E1]"
                        ),
                    }],
                },
            }],
        }

    monkeypatch.setattr(
        gateway,
        "_enviar",
        enviar,
    )

    sesion = gateway.planificar(
        "¿Cuántas cuentas tengo?",

        {"cuentas": {"nombre": "texto"}},

        herramienta,

        "Instrucciones de prueba",

        "gemini-3.5-flash-lite",

        None,
    )

    respuesta = (
        gateway.responder_con_evidencia(
            sesion,

            [{
                "referencia": "E1",
                "filas": [{"valor": 2}],
            }],

            None,
        )
    )

    assert "2 cuentas" in respuesta

    assert enviados[0]["tools"]

    continuacion = enviados[1]["contents"]

    assert (
        continuacion[1]["parts"][0][
            "thoughtSignature"
        ]

        == "firma-simulada"
    )

    assert (
        continuacion[2]["parts"][0][
            "functionResponse"
        ]["response"]["resultados"][0][
            "referencia"
        ]

        == "E1"
    )


def test_279_gemini_tokens_agotados():

    with pytest.raises(
        gateway.IANoDisponible
    ) as error:

        gateway._extraer_texto({
            "candidates": [{
                "finishReason": "MAX_TOKENS",
            }],
        })

    assert "tokens" in str(error.value).lower()


# ======================================
# AUTORIZACION Y ERRORES
# ======================================

def test_279_sin_consentimiento(
    monkeypatch,
):

    monkeypatch.setattr(
        gateway,
        "planificar",
        no_llamar,
    )

    monkeypatch.setattr(
        rag_service,
        "obtener_nombres_privados",
        no_llamar,
    )

    with pytest.raises(
        rag_service.ErrorRAG
    ) as error:

        rag_service.responder_asistente(
            object(),

            7,

            "¿Cuántas cuentas tengo?",

            False,
        )

    assert error.value.codigo == 403


def test_279_cuota_agotada_sin_respaldo(
    monkeypatch,
):

    monkeypatch.setattr(
        gateway,

        "comprobar_configuracion",

        lambda: "gemini-3.5-flash-lite",
    )

    monkeypatch.setattr(
        rag_service,

        "obtener_nombres_privados",

        lambda *args: [],
    )

    def cuota(*args, **kwargs):

        raise gateway.IANoDisponible(
            "Cuota Gemini agotada",

            codigo_http=429,
        )

    monkeypatch.setattr(
        gateway,
        "planificar",
        cuota,
    )

    monkeypatch.setattr(
        rag_service,
        "recuperar_plan",
        no_llamar,
    )

    with pytest.raises(
        rag_service.ErrorRAG
    ) as error:

        rag_service.responder_asistente(
            object(),

            7,

            "¿Cuánto gasté este mes?",

            True,
        )

    assert error.value.codigo == 429


def test_279_referencias_inventadas_rechazadas():

    with pytest.raises(
        rag_service.ErrorRAG
    ):

        rag_service._validar_referencias(
            "Tienes $500.000. [E99]",

            [{
                "referencia": "E1",
            }],
        )


def test_279_rdf_antiguo_rechazado(
    monkeypatch,
):

    monkeypatch.setattr(
        retrieval,

        "asegurar_actualizacion_para_rag",

        lambda *args: None,
    )

    monkeypatch.setattr(
        retrieval,

        "obtener_contexto_semantico_basico",

        lambda **kwargs: {
            "fecha_instantanea": (
                "2020-01-01T00:00:00+00:00"
            ),
        },
    )

    with pytest.raises(
        retrieval.ErrorRAG
    ) as error:

        retrieval._preparar_semantica(
            object(),
            7,
        )

    assert error.value.codigo == 409


def test_279_endpoint_requiere_jwt(client):

    respuesta = client.post(
        f"{RUTA}/preguntar",

        json={
            "pregunta": (
                "¿Qué movimientos tengo registrados?"
            ),

            "autorizo_envio_ia": True,
        },
    )

    assert respuesta.status_code == 401


# ======================================
# INTEGRACION HIBRIDA
# ======================================

def test_279_integracion_sql_y_rdf(
    client,
    db_session,
    monkeypatch,
):

    usuario, headers = (
        crear_usuario_autenticado(
            client,

            db_session,

            "qa.279.integracion@example.com",
        )
    )

    # Habilitar IA solo para esta cuenta ficticia.
    # El gateway de Gemini se simula en esta prueba.
    monkeypatch.setenv("RAG_IA_HABILITADA", "1")
    monkeypatch.setenv(
        "RAG_DEMO_USUARIOS", str(usuario.id_usuario)
    )

    crear_cuenta(
        db_session,

        usuario.id_usuario,

        "Caja privada integracion",

        "75000.00",
    )

    monkeypatch.setattr(
        gateway,

        "comprobar_configuracion",

        lambda: "gemini-3.5-flash-lite",
    )

    monkeypatch.setattr(
        retrieval,

        "asegurar_actualizacion_para_rag",

        lambda *args: None,
    )

    fecha = datetime.now(
        timezone.utc
    ).isoformat()

    sparql_ejecutado = []

    def consultar(sparql):

        sparql_ejecutado.append(sparql)

        if "SELECT ?fecha" in sparql:

            return [{
                "fecha": {
                    "type": "literal",
                    "value": fecha,
                },
            }]

        if "fin:correspondeAMeta" in sparql:

            return [{
                "cuenta": {
                    "type": "literal",

                    "value": (
                        "Caja privada integracion"
                    ),
                },

                "meta": {
                    "type": "literal",

                    "value": "Meta semantica",
                },
            }]

        raise AssertionError(
            "Consulta SPARQL inesperada"
        )

    monkeypatch.setattr(
        retrieval,
        "consultar_select",
        consultar,
    )

    def planificar(*args, **kwargs):

        return {
            "modelo": "gemini-3.5-flash-lite",

            "argumentos": {
                "estado": "consultar",

                "consultas": [
                    {
                        "entidad": "cuentas",

                        "operacion": "sumar",

                        "campo": "saldo_libre",
                    },
                    {
                        "entidad": "rdf_reservas",

                        "operacion": "listar",

                        "campos": [
                            "cuenta",
                            "meta",
                        ],
                    },
                ],
            },
        }

    monkeypatch.setattr(
        gateway,
        "planificar",
        planificar,
    )

    def generar(
        sesion,
        evidencia,
        limite,
    ):

        assert [
            resultado["origen"]

            for resultado in evidencia

        ] == [
            "PostgreSQL",
            "Fuseki/SPARQL",
        ]

        assert (
            evidencia[0]["filas"][0]["valor"]
            == "75000.00"
        )

        enviado = json.dumps(
            evidencia,
            ensure_ascii=False,
        )

        assert (
            "Caja privada integracion"
            not in enviado
        )

        return (
            "Tu saldo libre es $75.000 COP. [E1] "
            "Hay evidencia de relaciones entre "
            "cuentas y metas. [E2]"
        )

    monkeypatch.setattr(
        gateway,

        "responder_con_evidencia",

        generar,
    )

    respuesta = client.post(
        f"{RUTA}/preguntar",

        headers=headers,

        json={
            "pregunta": (
                "¿Cuál es mi saldo y cómo se "
                "relacionan mis cuentas con mis metas?"
            ),

            "autorizo_envio_ia": True,
        },
    )

    assert respuesta.status_code == 200

    datos = respuesta.json()

    assert (
        datos["metodo"]
        == "RAG_SQL_SPARQL"
    )

    assert len(datos["evidencia"]) == 2

    assert len(sparql_ejecutado) == 2

    assert all(
        (
            "GRAPH <urn:finanzas:grafo:usuario:"
            f"{usuario.id_usuario}>"
        ) in consulta

        for consulta in sparql_ejecutado
    )


def test_279_pregunta_no_soportada(
    monkeypatch,
):

    monkeypatch.setattr(
        gateway,

        "comprobar_configuracion",

        lambda: "gemini-3.5-flash-lite",
    )

    monkeypatch.setattr(
        rag_service,

        "obtener_nombres_privados",

        lambda *args: [],
    )

    monkeypatch.setattr(
        gateway,

        "planificar",

        lambda *args: {
            "argumentos": {
                "estado": "no_soportado",

                "consultas": [],
            },
        },
    )

    monkeypatch.setattr(
        rag_service,

        "recuperar_plan",

        no_llamar,
    )

    respuesta = rag_service.responder_asistente(
        object(),

        7,

        "Transfiere dinero a mi cuenta.",

        True,
    )

    assert (
        respuesta["metodo"]
        == "RAG_SIN_EVIDENCIA"
    )

    assert respuesta["evidencia"] == []