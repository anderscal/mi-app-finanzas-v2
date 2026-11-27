"""Cliente interno de Fuseki; nunca exponer a la PWA."""

import base64
import json
import os
import re
import ssl

from urllib.error import HTTPError, URLError

from urllib.parse import urlencode, urlsplit

from urllib.request import (
    Request,
    build_opener,
    HTTPSHandler,
    HTTPRedirectHandler,
    ProxyHandler,
)

import certifi

from rdflib import Graph


class FusekiNoDisponible(Exception):

    pass


class SinRedireccion(HTTPRedirectHandler):

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):

        return None


def _configuracion():

    url = os.getenv(

        "FUSEKI_BASE_URL",

        "http://127.0.0.1:3030"

    ).rstrip("/")


    try:

        partes = urlsplit(url)

        puerto = partes.port

        if (
            not partes.hostname

            or partes.username is not None

            or partes.password is not None

            or partes.path

            or partes.query

            or partes.fragment

            or puerto == 0

            or any(
                c.isspace() or ord(c) < 32
                for c in url
            )

            or any(
                c in url for c in "?#\\"
            )
        ):

            raise ValueError()

    except ValueError:

        raise ValueError(
            "FUSEKI_BASE_URL invalida"
        ) from None


    usuario = os.getenv(
        "FUSEKI_USER", ""
    )

    password = os.getenv(
        "FUSEKI_PASSWORD", ""
    )


    # HTTP exclusivamente para desarrollo local.

    if partes.scheme == "http" and partes.hostname in {

        "127.0.0.1",

        "localhost",

        "::1",

    }:

        if usuario or password:

            raise ValueError(
                "No enviar credenciales Fuseki por HTTP"
            )

        return url + "/finanzas_demo", None


    # Toda conexion remota requiere HTTPS.

    if partes.scheme != "https":

        raise ValueError(
            "Fuseki remoto requiere HTTPS"
        )


    if (
        not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,64}",
            usuario,
        )

        or not re.fullmatch(
            r"[A-Za-z0-9_-]{32,128}",
            password,
        )
    ):

        raise ValueError(
            "Credenciales Fuseki HTTPS invalidas"
        )


    credencial = base64.b64encode(

        f"{usuario}:{password}".encode("ascii")

    ).decode("ascii")


    return (

        url + "/finanzas_demo",

        "Basic " + credencial,
    )


def _base():

    return _configuracion()[0]


def _solicitar(solicitud: Request) -> bytes:

    base, autorizacion = _configuracion()


    if not solicitud.full_url.startswith(
        base + "/"
    ):

        raise ValueError(
            "Destino Fuseki no autorizado"
        )


    if autorizacion:

        solicitud.add_unredirected_header(

            "Authorization",

            autorizacion,
        )


    try:

        contexto = ssl.create_default_context(

            cafile=certifi.where()
        )


        cliente = build_opener(

            ProxyHandler({}),

            SinRedireccion(),

            HTTPSHandler(context=contexto),
        )


        with cliente.open(

            solicitud,

            timeout=12,

        ) as respuesta:

            return respuesta.read()


    except (

        HTTPError,

        URLError,

        OSError,

        TimeoutError,

    ) as exc:

        raise FusekiNoDisponible(

            "No fue posible comunicarse con Fuseki"

        ) from exc


def publicar_grafo(
    grafo: Graph,
    iri: str,
) -> None:

    destino = (

        _base()

        + "/data?"

        + urlencode({
            "graph": iri
        })
    )


    ttl = grafo.serialize(
        format="turtle"
    ).encode("utf-8")


    peticion = Request(

        destino,

        data=ttl,

        method="PUT",

        headers={
            "Content-Type":
                "text/turtle; charset=utf-8"
        },
    )


    _solicitar(peticion)


def consultar_select(consulta: str) -> list[dict]:

    peticion = Request(

        _base() + "/sparql",

        data=urlencode({

            "query": consulta

        }).encode("utf-8"),

        method="POST",

        headers={

            "Content-Type":
                "application/x-www-form-urlencoded",

            "Accept":
                "application/sparql-results+json",
        },
    )


    try:

        contenido = json.loads(

            _solicitar(peticion).decode("utf-8")
        )

        return contenido["results"]["bindings"]


    except (

        ValueError,

        KeyError,

        TypeError,

    ) as exc:

        raise FusekiNoDisponible(

            "Respuesta SPARQL invalida"

        ) from exc