
"""Pruebas 26.4: aislamiento, RDF y endpoints, sin escribir en Fuseki real."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from rdflib import RDF, URIRef

from app.business.semantica_service import FIN, OP, iri_grafo
from app.tests.helpers import (
    crear_cuenta,
    crear_usuario_autenticado,
    obtener_categoria_sistema,
)

RUTA = '/consultas/semantica'


def test_264_requiere_jwt(client):
    assert client.post(f'{RUTA}/sincronizar').status_code == 401
    assert client.get(f'{RUTA}/cuentas').status_code == 401


def test_264_sincroniza_solo_grafo_del_usuario(client, db_session, monkeypatch):
    usuario1, headers1 = crear_usuario_autenticado(
        client, db_session, 'qa.264.uno@example.com'
    )
    usuario2, headers2 = crear_usuario_autenticado(
        client, db_session, 'qa.264.dos@example.com'
    )
    cuenta1 = crear_cuenta(db_session, usuario1.id_usuario, 'Caja Uno RDF', '1500.00')
    cuenta2 = crear_cuenta(db_session, usuario2.id_usuario, 'Caja Dos RDF', '900.00')

    monkeypatch.setenv("SEMANTICA_EXPORTACION_LOCAL", "1")
    publicados = []
    monkeypatch.setattr(
        'app.business.semantica_auto_sync.publicar_grafo',
        lambda grafo, iri: publicados.append((grafo, iri)),
    )

    r1 = client.post(f'{RUTA}/sincronizar', headers=headers1)
    r2 = client.post(f'{RUTA}/sincronizar', headers=headers2)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r1.json()['entidades']['cuentas'] == 1
    assert r2.json()['entidades']['cuentas'] == 1
    assert len(publicados) == 2

    g1, iri1 = publicados[0]
    g2, iri2 = publicados[1]
    assert iri1 == iri_grafo(usuario1.id_usuario)
    assert iri2 == iri_grafo(usuario2.id_usuario)
    assert iri1 != iri2

    nombres1 = {str(x) for x in g1.objects(None, FIN.tieneNombreCuenta)}
    nombres2 = {str(x) for x in g2.objects(None, FIN.tieneNombreCuenta)}
    assert nombres1 == {'Caja Uno RDF'}
    assert nombres2 == {'Caja Dos RDF'}
    assert str(cuenta1.id_cuenta) not in nombres2
    assert str(cuenta2.id_cuenta) not in nombres1
    assert b'password_hash' not in g1.serialize(format='turtle').encode('utf-8')
    assert 'qa.264.uno@example.com' not in g1.serialize(format='turtle')


def test_264_reserva_y_gmf_en_grafo(client, db_session, monkeypatch):
    usuario, headers = crear_usuario_autenticado(
        client, db_session, 'qa.264.reserva@example.com'
    )
    cuenta = crear_cuenta(db_session, usuario.id_usuario, 'Caja Meta RDF', '1000.00')
    categoria = obtener_categoria_sistema(db_session, 'GASTO')
    meta = client.post('/metas/', headers=headers, json={
        'nombre_meta': 'Objetivo RDF',
        'monto_objetivo': '500.00',
        'fecha_objetivo': (date.today() + timedelta(days=30)).isoformat(),
        'descripcion': 'Prueba 26.4',
    })
    assert meta.status_code == 201, meta.text
    id_meta = meta.json()['id_meta']
    reserva = client.post(f'/metas/{id_meta}/reservas', headers=headers, json={
        'uuid_operacion': str(uuid4()),
        'id_cuenta': cuenta.id_cuenta,
        'monto': '200.00',
        'fecha_operacion': date.today().isoformat(),
    })
    assert reserva.status_code == 201, reserva.text
    gasto = client.post('/movimientos/normales', headers=headers, json={
        'uuid_local': str(uuid4()),
        'id_cuenta': cuenta.id_cuenta,
        'id_categoria': categoria.id_categoria,
        'tipo': 'GASTO',
        'monto': '100.00',
        'aplica_gmf': True,
        'fecha_movimiento': date.today().isoformat(),
        'descripcion': 'Ejemplo sin publicar',
    })
    assert gasto.status_code == 200, gasto.text

    monkeypatch.setenv("SEMANTICA_EXPORTACION_LOCAL", "1")
    capturados = []
    monkeypatch.setattr(
        'app.business.semantica_auto_sync.publicar_grafo',
        lambda grafo, iri: capturados.append(grafo),
    )
    respuesta = client.post(f'{RUTA}/sincronizar', headers=headers)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()['entidades']['aportes'] == 1
    g = capturados[0]
    assert list(g.subjects(RDF.type, FIN.ReservaMeta))
    assert Decimal(str(next(g.objects(None, FIN.tieneMontoReservado)))) == Decimal('200.00')
    assert Decimal(str(next(g.objects(None, FIN.tieneSaldoLibre)))) == Decimal('699.60')
    assert any(Decimal(str(x)) == Decimal('0.40') for x in g.objects(None, OP.montoGMF))
    assert 'Ejemplo sin publicar' not in g.serialize(format='turtle')


def test_264_consulta_sparql_solo_grafo_propio(client, db_session, monkeypatch):
    usuario, headers = crear_usuario_autenticado(
        client, db_session, 'qa.264.consulta@example.com'
    )
    consultas = []

    def simular(consulta):
        consultas.append(consulta)
        return [{
            'id': {'value': '37'},
            'nombre': {'value': 'Cuenta test'},
            'real': {'value': '900.00'},
            'reservado': {'value': '300.00'},
            'libre': {'value': '600.00'},
        }]

    monkeypatch.setattr('app.persistence.semantica_consulta_repository.consultar_select', simular)
    r = client.get(f'{RUTA}/cuentas', headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()['cuentas'][0]['saldo_libre'] == '600.00'
    assert r.json()['actualizacion_automatica'] is False
    assert f'GRAPH <{iri_grafo(usuario.id_usuario)}>' in consultas[0]
    assert 'GRAPH ?' not in consultas[0]


def test_264_consulta_inconsistente_rechazada(client, db_session, monkeypatch):
    _, headers = crear_usuario_autenticado(
        client, db_session, 'qa.264.inconsistente@example.com'
    )
    monkeypatch.setattr(
        'app.persistence.semantica_consulta_repository.consultar_select',
        lambda _: [{
            'id': {'value': '1'},
            'nombre': {'value': 'Cuenta'},
            'real': {'value': '100.00'},
            'reservado': {'value': '80.00'},
            'libre': {'value': '50.00'},
        }],
    )
    r = client.get(f'{RUTA}/cuentas', headers=headers)
    assert r.status_code == 502
