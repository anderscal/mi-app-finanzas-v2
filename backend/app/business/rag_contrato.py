"""Contrato autorizado de consultas RAG. Business.

Paso 27.9 A.2.
Normalizacion previa a la validacion estricta.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)


CATALOGO = {
    "cuentas": {
        "nombre": "texto",
        "tipo": "texto",
        "estado": "texto",
        "saldo_real": "decimal",
        "reservado": "decimal",
        "saldo_libre": "decimal",
    },
    "movimientos": {
        "fecha": "fecha",
        "tipo": "texto",
        "origen": "texto",
        "estado": "texto",
        "cuenta": "texto",
        "tipo_cuenta": "texto",
        "categoria": "texto",
        "obligacion": "texto",
        "monto": "decimal",
        "gmf": "decimal",
        "monto_con_gmf": "decimal",
    },
    "transferencias": {
        "fecha": "fecha",
        "cuenta_origen": "texto",
        "cuenta_destino": "texto",
        "estado": "texto",
        "monto": "decimal",
        "gmf": "decimal",
    },
    "obligaciones": {
        "nombre": "texto",
        "tipo": "texto",
        "estado": "texto",
        "fecha_inicio": "fecha",
        "fecha_vencimiento": "fecha",
        "monto_original": "decimal",
        "abonado": "decimal",
        "pendiente": "decimal",
    },
    "metas": {
        "nombre": "texto",
        "estado": "texto",
        "fecha_objetivo": "fecha",
        "objetivo": "decimal",
        "acumulado": "decimal",
        "progreso": "decimal",
    },
    "presupuestos": {
        "categoria": "texto",
        "anio": "entero",
        "mes": "entero",
        "limite": "decimal",
        "gastado": "decimal",
        "disponible": "decimal",
        "porcentaje_usado": "decimal",
    },
    "reservas": {
        "meta": "texto",
        "cuenta": "texto",
        "reservado_neto": "decimal",
    },
    "categorias": {
        "nombre": "texto",
        "tipo": "texto",
        "estado": "texto",
    },
    "rdf_reservas": {
        "meta": "texto",
        "cuenta": "texto",
        "tipo": "texto",
        "estado": "texto",
        "fecha": "fecha",
    },
    "rdf_movimientos": {
        "cuenta": "texto",
        "categoria": "texto",
        "obligacion": "texto",
        "tipo": "texto",
        "origen": "texto",
        "estado": "texto",
        "fecha": "fecha",
    },
    "rdf_transferencias": {
        "cuenta_origen": "texto",
        "cuenta_destino": "texto",
        "estado": "texto",
    },
    "rdf_categorias": {
        "nombre": "texto",
        "clase": "texto",
        "estado": "texto",
    },
    "rdf_obligaciones": {
        "nombre": "texto",
        "clase": "texto",
        "estado": "texto",
    },
    "rdf_presupuestos": {
        "categoria": "texto",
        "anio": "entero",
        "mes": "entero",
    },
}


CAMPOS_PREDETERMINADOS = {
    "cuentas": (
        "nombre", "tipo", "estado",
        "saldo_real", "reservado", "saldo_libre",
    ),
    "movimientos": (
        "fecha", "tipo", "origen", "estado",
        "cuenta", "categoria", "monto", "gmf",
    ),
    "transferencias": (
        "fecha", "cuenta_origen",
        "cuenta_destino", "estado", "monto", "gmf",
    ),
    "obligaciones": (
        "nombre", "tipo", "estado",
        "fecha_inicio", "fecha_vencimiento",
        "monto_original", "abonado", "pendiente",
    ),
    "metas": (
        "nombre", "estado", "fecha_objetivo",
        "objetivo", "acumulado", "progreso",
    ),
    "presupuestos": (
        "categoria", "anio", "mes", "limite",
        "gastado", "disponible", "porcentaje_usado",
    ),
    "reservas": (
        "meta", "cuenta", "reservado_neto",
    ),
    "categorias": (
        "nombre", "tipo", "estado",
    ),
    "rdf_reservas": (
        "meta", "cuenta", "tipo", "estado", "fecha",
    ),
    "rdf_movimientos": (
        "cuenta", "categoria", "obligacion",
        "tipo", "origen", "estado", "fecha",
    ),
    "rdf_transferencias": (
        "cuenta_origen", "cuenta_destino", "estado",
    ),
    "rdf_categorias": (
        "nombre", "clase", "estado",
    ),
    "rdf_obligaciones": (
        "nombre", "clase", "estado",
    ),
    "rdf_presupuestos": (
        "categoria", "anio", "mes",
    ),
}


OPERACIONES = (
    "listar",
    "contar",
    "sumar",
    "promedio",
    "minimo",
    "maximo",
)

AGREGACIONES_MONETARIAS = (
    "sumar",
    "promedio",
    "minimo",
    "maximo",
)

OPERADORES = (
    "igual",
    "distinto",
    "mayor",
    "menor",
    "mayor_igual",
    "menor_igual",
    "contiene",
    "es_nulo",
    "no_nulo",
)

OPERADORES_NULOS = {
    "es_nulo",
    "no_nulo",
}

MAX_CONSULTAS = 6
MAX_FILAS = 50
MAX_CAMPOS = 8


class Contrato(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )


def valor_tipado(tipo, valor):

    if not isinstance(valor, str) or len(valor) > 200:
        raise ValueError("Valor de filtro inválido")

    if tipo == "texto":
        return valor

    if tipo == "fecha":

        convertido = date.fromisoformat(valor)

        if convertido.isoformat() != valor:
            raise ValueError("Fecha inválida")

        return convertido

    if tipo == "entero":

        convertido = int(valor)

        if abs(convertido) > 1000000000:
            raise ValueError("Entero fuera de rango")

        return convertido

    if tipo == "decimal":

        try:
            convertido = Decimal(valor)

        except InvalidOperation as error:
            raise ValueError("Importe inválido") from error

        if (
            not convertido.is_finite()
            or abs(convertido)
            > Decimal("1000000000000000000")
        ):
            raise ValueError("Importe fuera de rango")

        return convertido

    raise ValueError("Tipo de campo no autorizado")


class Filtro(Contrato):

    campo: StrictStr

    operador: Literal[
        "igual",
        "distinto",
        "mayor",
        "menor",
        "mayor_igual",
        "menor_igual",
        "contiene",
        "es_nulo",
        "no_nulo",
    ]

    valor: StrictStr = ""


class Consulta(Contrato):

    entidad: StrictStr

    operacion: Literal[
        "listar",
        "contar",
        "sumar",
        "promedio",
        "minimo",
        "maximo",
    ]

    campos: list[StrictStr] = Field(
        default_factory=list,
        max_length=MAX_CAMPOS,
    )

    campo: StrictStr = ""

    filtros: list[Filtro] = Field(
        default_factory=list,
        max_length=12,
    )

    agrupar_por: list[StrictStr] = Field(
        default_factory=list,
        max_length=3,
    )

    orden_campo: StrictStr = ""

    descendente: StrictBool = False

    limite: StrictInt = Field(
        default=20,
        ge=1,
        le=MAX_FILAS,
    )

    # ==========================================
    # FASE 1: NORMALIZACION PREVIA
    # ==========================================

    @model_validator(mode="before")
    @classmethod
    def normalizar_entrada(cls, entrada):

        if not isinstance(entrada, dict):
            return entrada

        # No modificar el plan original recibido.
        datos = dict(entrada)

        operacion = datos.get("operacion")
        entidad = datos.get("entidad")
        campo = datos.get("campo")
        orden = datos.get("orden_campo")

        grupos = datos.get(
            "agrupar_por", []
        )

        # Proyeccion predeterminada para listados.
        # Solo se completa si esta ausente o vacia.
        # Los tipos invalidos no se corrigen.

        if (
            operacion == "listar"
            and isinstance(entidad, str)
            and entidad in CAMPOS_PREDETERMINADOS
            and (
                "campos" not in datos
                or datos["campos"] == []
            )
        ):

            datos["campos"] = list(
                CAMPOS_PREDETERMINADOS[entidad]
            )

        # Normalizacion del alias de agregacion.
        # SUM(monto), AVG(monto), etc. producen
        # una columna denominada valor.

        if (
            operacion in AGREGACIONES_MONETARIAS
            and isinstance(campo, str)
            and campo
            and orden == campo
            and isinstance(grupos, list)
            and campo not in grupos
        ):

            datos["orden_campo"] = "valor"

        # Se aplica el orden descendente por defecto
        # solo a resultados agregados y cuando
        # Gemini no proporciona direccion.

        if (
            operacion in (
                "contar",
                "sumar",
                "promedio",
                "minimo",
                "maximo",
            )
            and datos.get("orden_campo")
            in ("valor", "cantidad")
            and "descendente" not in datos
        ):

            datos["descendente"] = True

        return datos

    # ==========================================
    # FASE 2: VALIDACION ESTRICTA
    # ==========================================

    @model_validator(mode="after")
    def validar_consulta(self):

        disponibles = CATALOGO.get(
            self.entidad
        )

        if disponibles is None:
            raise ValueError("Entidad no autorizada")

        if len(self.campos) > MAX_CAMPOS:
            raise ValueError("Demasiados campos solicitados")

        for lista in (
            self.campos,
            self.agrupar_por,
        ):

            if len(lista) != len(set(lista)):
                raise ValueError("Campos duplicados")

            if any(
                campo not in disponibles
                for campo in lista
            ):
                raise ValueError("Campo no autorizado")

        if self.operacion == "listar":

            if not self.campos:
                raise ValueError(
                    "Un listado requiere campos"
                )

            if self.agrupar_por or self.campo:

                raise ValueError(
                    "Listado incompatible con agregación"
                )

            ordenables = disponibles

        else:

            if self.campos:

                raise ValueError(
                    "No usar campos en agregaciones"
                )

            if self.operacion == "contar":

                if self.campo:

                    raise ValueError(
                        "Contar no requiere campo"
                    )

            elif disponibles.get(self.campo) != "decimal":

                raise ValueError(
                    "La agregación requiere un campo "
                    "monetario o indicador decimal autorizado"
                )

            ordenables = {
                *self.agrupar_por,
                "valor",
                "cantidad",
            }

        if (
            self.entidad.startswith("rdf_")
            and self.operacion not in {
                "listar",
                "contar",
            }
        ):

            raise ValueError(
                "Las agregaciones monetarias "
                "se realizan en SQL"
            )

        if (
            self.orden_campo
            and self.orden_campo not in ordenables
        ):

            raise ValueError(
                "Ordenamiento no autorizado"
            )

        for filtro in self.filtros:

            tipo = disponibles.get(
                filtro.campo
            )

            if tipo is None:

                raise ValueError(
                    "Campo de filtro no autorizado"
                )

            if filtro.operador in OPERADORES_NULOS:

                if filtro.valor:

                    raise ValueError(
                        "El operador nulo "
                        "no requiere valor"
                    )

                continue

            if (
                filtro.operador == "contiene"
                and tipo != "texto"
            ):

                raise ValueError(
                    "Contiene solo admite texto"
                )

            if (
                tipo == "texto"
                and filtro.operador not in {
                    "igual",
                    "distinto",
                    "contiene",
                }
            ):

                raise ValueError(
                    "Comparación textual no autorizada"
                )

            valor_tipado(
                tipo,
                filtro.valor,
            )

        return self


class PlanConsulta(Contrato):

    estado: Literal[
        "consultar",
        "aclarar",
        "no_soportado",
    ]

    consultas: list[Consulta] = Field(
        default_factory=list,
        max_length=MAX_CONSULTAS,
    )

    mensaje: StrictStr = Field(
        default="",
        max_length=400,
    )

    @model_validator(mode="after")
    def validar_plan(self):

        if self.estado == "consultar":

            if not self.consultas:

                raise ValueError(
                    "El plan debe contener consultas"
                )

        elif self.consultas:

            raise ValueError(
                "Una aclaración no puede ejecutar consultas"
            )

        return self


def declaracion_herramienta():
    """Contrato de function calling enviado a Gemini."""

    return {
        "name": "planificar_consultas_financieras",

        "description": (
            "Construye consultas financieras de solo "
            "lectura sobre PostgreSQL y Fuseki. "
            "Utiliza exclusivamente el catálogo autorizado. "

            "Para listar selecciona campos pertinentes. "
            "Si se omiten, se aplican los predeterminados. "

            "Para sumar, promedio, minimo y maximo "
            "indica el campo decimal que deseas agregar. "

            "Para ordenar una agregación utiliza "
            "orden_campo igual a valor. "
            "Indica descendente=true para mayores valores "
            "y descendente=false para menores valores. "

            "En resúmenes financieros sin periodo explícito "
            "utiliza el mes actual según la fecha de referencia. "
            "Indica siempre el periodo realmente consultado. "

            "Los movimientos recientes sin periodo pueden "
            "recuperarse de todo el historial. "

            "Los gastos ordinarios por categoría incluyen "
            "su GMF salvo que el usuario pida excluirlo. "
            "Utiliza monto_con_gmf, tipo GASTO, "
            "origen NORMAL y estado ACTIVO. "

            "Expresa los importes en pesos colombianos "
            "con formato como $50.000,00 COP. "
            "Conserva exactamente los alias privados."
        ),

        "parameters": {
            "type": "OBJECT",

            "properties": {

                "estado": {
                    "type": "STRING",
                    "enum": [
                        "consultar",
                        "aclarar",
                        "no_soportado",
                    ],
                },

                "mensaje": {
                    "type": "STRING",
                    "description": (
                        "Aclaración o explicación breve "
                        "cuando no sea posible consultar."
                    ),
                },

                "consultas": {
                    "type": "ARRAY",

                    "items": {
                        "type": "OBJECT",

                        "properties": {

                            "entidad": {
                                "type": "STRING",
                                "enum": list(CATALOGO),
                            },

                            "operacion": {
                                "type": "STRING",
                                "enum": list(OPERACIONES),
                            },

                            "campos": {
                                "type": "ARRAY",

                                "description": (
                                    "Hasta ocho campos para listar. "
                                    "Si se omiten se aplican los "
                                    "predeterminados. "
                                    "No usar en agregaciones."
                                ),

                                "items": {
                                    "type": "STRING",
                                },
                            },

                            "campo": {
                                "type": "STRING",

                                "description": (
                                    "Campo decimal requerido "
                                    "para sumar, promedio, "
                                    "minimo o maximo. "
                                    "No usar para listar ni contar."
                                ),
                            },

                            "filtros": {
                                "type": "ARRAY",

                                "items": {
                                    "type": "OBJECT",

                                    "properties": {

                                        "campo": {
                                            "type": "STRING",
                                        },

                                        "operador": {
                                            "type": "STRING",
                                            "enum": list(OPERADORES),
                                        },

                                        "valor": {
                                            "type": "STRING",

                                            "description": (
                                                "Valor textual, "
                                                "numérico sin separadores "
                                                "de miles o fecha YYYY-MM-DD."
                                            ),
                                        },
                                    },

                                    "required": [
                                        "campo",
                                        "operador",
                                    ],
                                },
                            },

                            "agrupar_por": {
                                "type": "ARRAY",

                                "description": (
                                    "Campos de agrupación "
                                    "para agregaciones."
                                ),

                                "items": {
                                    "type": "STRING",
                                },
                            },

                            "orden_campo": {
                                "type": "STRING",

                                "description": (
                                    "Campo autorizado para ordenar. "
                                    "En agregaciones usa valor "
                                    "para el resultado calculado, "
                                    "cantidad para el número de "
                                    "registros o un campo de agrupación."
                                ),
                            },

                            "descendente": {
                                "type": "BOOLEAN",

                                "description": (
                                    "Indica true para mayores "
                                    "o recientes y false para "
                                    "menores o antiguos. "
                                    "Si se omite al ordenar por "
                                    "valor o cantidad agregada, "
                                    "se aplica orden descendente."
                                ),
                            },

                            "limite": {
                                "type": "INTEGER",

                                "description": (
                                    "Máximo de filas entre 1 y 50."
                                ),
                            },
                        },

                        "required": [
                            "entidad",
                            "operacion",
                        ],
                    },
                },
            },

            "required": [
                "estado",
                "consultas",
            ],
        },
    }


def preparar_consulta(
    consulta,
    restaurar_valor,
):

    datos = consulta.model_dump()

    for filtro in datos["filtros"]:

        if filtro["operador"] in OPERADORES_NULOS:

            filtro["valor"] = None
            continue

        tipo = CATALOGO[
            consulta.entidad
        ][filtro["campo"]]

        valor = filtro["valor"]

        if tipo == "texto":

            valor = restaurar_valor(valor)

        filtro["valor"] = valor_tipado(
            tipo,
            valor,
        )

    return datos