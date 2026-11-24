
"""Preparacion de evidencia y privacidad. Business.

Paso 27.9 A.2.
Restauracion segura de alias financieros conocidos.
"""

import re

from datetime import date, datetime
from decimal import Decimal


class RegistroAlias:

    def __init__(self, nombres):

        self.originales = {}
        self.alias_por_nombre = {}

        nombres = sorted(
            {
                nombre.strip()
                for nombre in nombres
                if isinstance(nombre, str)
                and nombre.strip()
            },
            key=lambda nombre: (
                -len(nombre),
                nombre.casefold(),
                nombre,
            ),
        )

        for nombre in nombres:

            clave = nombre.casefold()

            if clave in self.alias_por_nombre:
                continue

            alias = (
                f"Entidad_privada_"
                f"{len(self.originales) + 1:05d}"
            )

            self.originales[alias] = nombre

            self.alias_por_nombre[clave] = alias

        alternativas = [
            re.escape(nombre)
            for nombre in nombres
        ]

        self.patron = (
            re.compile(
                r"(?<!\w)(?:"
                + "|".join(alternativas)
                + r")(?!\w)",
                re.IGNORECASE,
            )
            if alternativas
            else None
        )

        # Reconoce el prefijo canonico y posibles
        # espacios accidentales entre sus caracteres.
        #
        # No realiza coincidencias aproximadas
        # entre identificadores numericos.

        prefijo = r"[ \t]*".join(
            re.escape(caracter)
            for caracter in "Entidad_privada_"
        )

        self.patron_alias = re.compile(
            r"(?<!\w)"
            + prefijo
            + r"[ \t]*(\d+)(?!\w)",
            re.IGNORECASE,
        )

    def proteger(self, texto):

        if not isinstance(texto, str):
            return texto

        if self.patron is None:
            return texto

        def reemplazar(coincidencia):

            nombre = coincidencia.group(0)

            return self.alias_por_nombre.get(
                nombre.casefold(),
                nombre,
            )

        return self.patron.sub(
            reemplazar,
            texto,
        )

    def _alias_canonico(self, coincidencia):

        return (
            "Entidad_privada_"
            + coincidencia.group(1)
        )

    def restaurar(self, texto):

        if not isinstance(texto, str):
            return texto

        def reemplazar(coincidencia):

            alias = self._alias_canonico(
                coincidencia
            )

            return self.originales.get(
                alias,
                coincidencia.group(0),
            )

        return self.patron_alias.sub(
            reemplazar,
            texto,
        )

    def restaurar_filtro(self, texto):

        if not isinstance(texto, str):

            raise ValueError(
                "Se esperaba un texto válido"
            )

        for coincidencia in (
            self.patron_alias.finditer(texto)
        ):

            alias = self._alias_canonico(
                coincidencia
            )

            if alias not in self.originales:

                raise ValueError(
                    "Alias financiero desconocido"
                )

        return self.restaurar(texto)


def serializar(valor):

    if valor is None:
        return None

    if isinstance(valor, Decimal):

        if not valor.is_finite():

            raise ValueError(
                "Valor financiero no finito"
            )

        return format(valor, "f")

    if isinstance(valor, (date, datetime)):
        return valor.isoformat()

    if isinstance(valor, (str, int, bool)):
        return valor

    if isinstance(valor, dict):

        return {
            clave: serializar(dato)
            for clave, dato in valor.items()
        }

    if isinstance(valor, (list, tuple)):

        return [
            serializar(dato)
            for dato in valor
        ]

    raise ValueError(
        "Tipo de evidencia no admitido"
    )


def proteger_evidencia(resultados, registro):

    campos_nombre = {
        "nombre",
        "cuenta",
        "cuenta_origen",
        "cuenta_destino",
        "meta",
        "categoria",
        "obligacion",
    }

    protegidos = []

    for resultado in resultados:

        copia = {
            **resultado,
            "filas": [],
        }

        for fila in resultado["filas"]:

            copia["filas"].append({

                campo: (
                    registro.proteger(valor)

                    if campo in campos_nombre
                    else valor
                )

                for campo, valor in fila.items()
            })

        copia["filtros"] = [
            {
                **filtro,

                "valor": registro.proteger(
                    filtro["valor"]
                ),
            }

            for filtro in resultado.get("filtros", [])
        ]

        protegidos.append(copia)

    return serializar(protegidos)

