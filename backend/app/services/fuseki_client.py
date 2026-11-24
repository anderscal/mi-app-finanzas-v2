
"""Cliente HTTP interno para Fuseki Plain local. No exponer a la PWA."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from rdflib import Graph


class FusekiNoDisponible(Exception):
    pass


def _base() -> str:
    url = os.getenv('FUSEKI_BASE_URL', 'http://127.0.0.1:3030').rstrip('/')
    partes = urlsplit(url)
    if (partes.scheme != 'http' or partes.hostname not in
            ('127.0.0.1', 'localhost') or partes.username or partes.password or
            partes.path not in ('', '/') or partes.query or partes.fragment):
        raise ValueError('FUSEKI_BASE_URL debe apuntar al servidor HTTP local')
    return url + '/finanzas_demo'


def _solicitar(solicitud: Request) -> bytes:
    try:
        with urlopen(solicitud, timeout=12) as respuesta:
            return respuesta.read()
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise FusekiNoDisponible('No fue posible comunicarse con Fuseki') from exc


def publicar_grafo(grafo: Graph, iri: str) -> None:
    """PUT GSP: reemplazo completo SOLO del grafo nombrado propio."""
    destino = _base() + '/data?' + urlencode({'graph': iri})
    ttl = grafo.serialize(format='turtle').encode('utf-8')
    peticion = Request(
        destino, data=ttl, method='PUT',
        headers={'Content-Type': 'text/turtle; charset=utf-8'},
    )
    _solicitar(peticion)


def consultar_select(consulta: str) -> list[dict]:
    peticion = Request(
        _base() + '/sparql',
        data=urlencode({'query': consulta}).encode('utf-8'),
        method='POST',
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/sparql-results+json',
        },
    )
    try:
        contenido = json.loads(_solicitar(peticion).decode('utf-8'))
        return contenido['results']['bindings']
    except (ValueError, KeyError, TypeError) as exc:
        raise FusekiNoDisponible('Respuesta SPARQL inválida') from exc
