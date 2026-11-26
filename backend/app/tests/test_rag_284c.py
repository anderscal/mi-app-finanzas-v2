import copy

import pytest

from app.business import rag_service as rag

from app.services import rag_ia_service as gateway

from app.business.rag_retrieval_service import ErrorRAG


VALIDO = {
    "estado": "consultar",

    "consultas": [{
        "entidad": "cuentas",
        "operacion": "sumar",
        "campo": "saldo_libre",
    }],
}


INVALIDO = {
    "estado": "consultar",

    "consultas": [{
        "entidad": "cuentas",
        "operacion": "sumar",
        "campo": "saldo_libre",
        "campos": ["nombre"],
    }],
}


@pytest.fixture
def flujo(monkeypatch):

    llamadas = []
    planes = []
    consultas = []
    respuestas = []

    monkeypatch.setattr(
        gateway,

        "comprobar_configuracion",

        lambda: "gemini-prueba",
    )

    monkeypatch.setattr(
        rag,

        "obtener_nombres_privados",

        lambda *a: ["Caja Secreta"],
    )


    def planificar(*args):

        llamadas.append(args)

        plan = planes.pop(0)

        if isinstance(plan, Exception):

            raise plan

        return {
            "argumentos": copy.deepcopy(plan),
            "marca": len(llamadas),
        }


    def recuperar(
        db,
        uid,
        plan,
        registro,
    ):

        consultas.append(
            (uid, plan)
        )

        return [{
            "referencia": "E1",

            "origen": "PostgreSQL",

            "filas": [{
                "valor": "50.00",
            }],

            "truncado": False,
        }]


    def responder(
        sesion,
        evidencia,
        limite,
    ):

        respuestas.append(
            (sesion, evidencia, limite)
        )

        return "$50 COP [E1]"


    monkeypatch.setattr(
        gateway,
        "planificar",
        planificar,
    )

    monkeypatch.setattr(
        rag,
        "recuperar_plan",
        recuperar,
    )

    monkeypatch.setattr(
        gateway,
        "responder_con_evidencia",
        responder,
    )

    return (
        planes,
        llamadas,
        consultas,
        respuestas,
    )


def ejecutar():

    return rag.responder_asistente(
        object(),

        7,

        "Saldo de Caja Secreta",

        True,
    )


# ======================================
# PLAN VALIDO
# ======================================

def test_valido_sin_reparacion(flujo):

    p, l, c, r = flujo

    p.append(VALIDO)

    assert (
        ejecutar()["respuesta"]
        == "$50 COP [E1]"
    )

    assert len(l) == len(c) == len(r) == 1


# ======================================
# REPARACION EXITOSA
# ======================================

def test_reparacion_exitosa(flujo):

    p, l, c, r = flujo

    p.extend([
        INVALIDO,
        VALIDO,
    ])

    assert (
        ejecutar()["metodo"]
        == "RAG_SQL"
    )

    assert len(l) == 2

    assert len(c) == len(r) == 1

    assert l[0][0] == l[1][0]

    assert "Caja Secreta" not in l[1][0]

    assert l[0][-1] == l[1][-1] == r[0][-1]

    assert "CORRECCION:" in l[1][3]

    assert r[0][0]["marca"] == 2

    assert c[0][0] == 7


# ======================================
# DOS PLANES INVALIDOS
# ======================================

def test_doble_invalido(flujo):

    p, l, c, r = flujo

    p.extend([
        INVALIDO,
        INVALIDO,
    ])

    with pytest.raises(ErrorRAG) as e:

        ejecutar()

    assert e.value.codigo == 422

    assert len(l) == 2

    assert not c

    assert not r


# ======================================
# ALIAS DESCONOCIDOS
# ======================================

def test_alias_desconocido(flujo):

    p, l, c, r = flujo

    invalido = copy.deepcopy(VALIDO)

    invalido["consultas"][0]["filtros"] = [{
        "campo": "nombre",

        "operador": "igual",

        "valor": "Entidad_privada_99999",
    }]

    p.extend([
        invalido,
        VALIDO,
    ])

    ejecutar()

    assert len(l) == 2

    assert len(c) == 1

    assert (
        "filtros: valor o alias no valido"
        in l[1][3]
    )

    assert (
        "Entidad_privada_99999"
        not in l[1][3]
    )


# ======================================
# PRIVACIDAD DEL DIAGNOSTICO
# ======================================

def test_diagnostico_sin_secretos(flujo):

    p, l, c, r = flujo

    invalido = copy.deepcopy(VALIDO)

    invalido["secreto_no_permitido"] = (
        "Caja Secreta"
    )

    p.extend([
        invalido,
        VALIDO,
    ])

    ejecutar()

    assert (
        "campo_no_autorizado"
        in l[1][3]
    )

    assert "Caja Secreta" not in l[1][3]

    assert (
        "secreto_no_permitido"
        not in l[1][3]
    )


# ======================================
# PREGUNTAS SIN CONSULTAS
# ======================================

@pytest.mark.parametrize(
    "estado",
    ["aclarar", "no_soportado"],
)
def test_sin_consulta(
    flujo,
    estado,
):

    p, l, c, r = flujo

    p.append({
        "estado": estado,

        "consultas": [],
    })

    assert ejecutar()["evidencia"] == []

    assert len(l) == 1

    assert not c

    assert not r


# ======================================
# CUOTA AGOTADA
# ======================================

def test_cuota_no_reparar(flujo):

    p, l, c, r = flujo

    p.append(
        gateway.IANoDisponible(
            "Cuota",
            codigo_http=429,
        )
    )

    with pytest.raises(ErrorRAG) as e:

        ejecutar()

    assert e.value.codigo == 429

    assert len(l) == 1

    assert not c

    assert not r


# ======================================
# PRESUPUESTO TEMPORAL
# ======================================

def test_plazo_agotado(
    flujo,
    monkeypatch,
):

    p, l, c, r = flujo

    p.append(INVALIDO)

    reloj = iter([
        0.0,
        0.0,
        0.0,
        46.0,
    ])

    monkeypatch.setattr(
        rag.time,

        "monotonic",

        lambda: next(reloj),
    )

    with pytest.raises(ErrorRAG) as e:

        ejecutar()

    assert e.value.codigo == 503

    assert len(l) == 1

    assert not c

    assert not r


# ======================================
# FALLO EN LA RECUPERACION
# ======================================

def test_error_recuperacion_no_replanificar(
    flujo,
    monkeypatch,
):

    p, l, c, r = flujo

    p.append(VALIDO)

    def fallo(*args):

        raise ErrorRAG(
            503,

            "Fuseki no disponible",
        )

    monkeypatch.setattr(
        rag,

        "recuperar_plan",

        fallo,
    )

    with pytest.raises(ErrorRAG) as e:

        ejecutar()

    assert e.value.codigo == 503

    assert len(l) == 1

    assert not r