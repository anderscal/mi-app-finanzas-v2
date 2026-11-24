
"""Auditoria operativa y arquitectonica del RAG.

Paso 27.8.

Ejecutar desde backend.

No modifica movimientos, cuentas, metas ni obligaciones.
Las solicitudes al asistente pueden activar su mecanismo
normal de sincronizacion RDF.

No registra tokens, nombres privados ni respuestas completas.
"""

import argparse
import ast
import getpass
import json
import statistics
import time
import tokenize

from collections import defaultdict

from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

from pathlib import Path

from urllib.error import (
    HTTPError,
    URLError,
)

from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)


BASE = (
    "http://127.0.0.1:8000"
    "/consultas/asistente"
)

RAIZ = (
    Path(__file__).resolve().parent
)

CERO = Decimal("0.00")

CENTAVO = Decimal("0.01")


ESCENARIOS = {

    "saldo": (
        "¿Cuánto dinero tengo disponible?"
    ),

    "obligaciones": (
        "¿Cuántas deudas tengo saldadas "
        "y cuánto dinero me deben?"
    ),

    "reservas": (
        "¿Cómo están distribuidas las reservas "
        "de mis metas entre las diferentes cuentas?"
    ),

    "general": (
        "Analiza mi situación financiera actual "
        "considerando mis cuentas, deudas, "
        "gastos, presupuestos y metas."
    ),
}


# =======================================
# INFORME DE RESULTADOS
# =======================================

class Informe:

    def __init__(self):

        self.correctos = 0

        self.fallos = 0

        self.revisiones = 0

    def comprobar(self, nombre, condicion):

        if condicion:

            self.correctos += 1

            print(
                f"[OK] {nombre}"
            )

        else:

            self.fallos += 1

            print(
                f"[FALLO] {nombre}"
            )

        return condicion

    def revisar(self, mensaje):

        self.revisiones += 1

        print(
            f"[REVISAR] {mensaje}"
        )

    def resumen(self):

        print("\n" + "=" * 60)

        print("RESUMEN DE AUDITORIA")

        print(
            f"Correctos: {self.correctos}"
        )

        print(
            f"Fallos: {self.fallos}"
        )

        print(
            f"Revisiones manuales: {self.revisiones}"
        )

        print("=" * 60)


# =======================================
# AUDITORIA ESTATICA DE CAPAS
# =======================================

CAPAS = {

    "routers": "Presentation",

    "business": "Business",

    "services": "Services",

    "persistence": "Persistence",
}


DEPENDENCIAS_A_REVISAR = {

    ("routers", "persistence"),

    ("business", "routers"),

    ("services", "business"),

    ("services", "routers"),

    ("persistence", "routers"),

    ("persistence", "business"),

    ("persistence", "services"),
}


def importaciones(arbol, paquete):

    from importlib.util import resolve_name

    for nodo in ast.walk(arbol):

        if isinstance(nodo, ast.Import):

            for alias in nodo.names:

                yield (
                    nodo.lineno,
                    alias.name,
                )

        elif isinstance(
            nodo,
            ast.ImportFrom,
        ):

            modulo = nodo.module or ""

            if nodo.level:

                nombre_relativo = (
                    "." * nodo.level
                    + modulo
                )

                try:

                    modulo = resolve_name(
                        nombre_relativo,
                        paquete,
                    )

                except (
                    ImportError,
                    ValueError,
                ):

                    continue

            if modulo:

                yield (
                    nodo.lineno,
                    modulo,
                )

                for alias in nodo.names:

                    yield (
                        nodo.lineno,

                        f"{modulo}.{alias.name}",
                    )


def capa_destino(importacion):

    partes = importacion.split(".")

    if (
        len(partes) >= 2

        and partes[0] == "app"

        and partes[1] in CAPAS
    ):

        return partes[1]

    return None


def auditar_arquitectura(informe):

    print("\nAUDITORIA DE ARQUITECTURA")
    print("-" * 60)

    app = RAIZ / "app"

    if not informe.comprobar(
        "Directorio app encontrado",

        app.is_dir(),
    ):

        return

    revisados = 0

    hallazgos = set()

    for origen in CAPAS:

        directorio = app / origen

        if not informe.comprobar(
            f"Capa {CAPAS[origen]} encontrada",

            directorio.is_dir(),
        ):

            continue

        for archivo in directorio.rglob(
            "*.py"
        ):

            ruta = archivo.relative_to(
                RAIZ
            )

            paquete = ".".join(
                archivo.parent.relative_to(
                    RAIZ
                ).parts
            )

            try:

                with tokenize.open(
                    str(archivo)
                ) as fuente:

                    arbol = ast.parse(
                        fuente.read()
                    )

            except (
                SyntaxError,
                UnicodeError,
                OSError,
            ):

                informe.comprobar(
                    f"Lectura y sintaxis: {ruta}",
                    False,
                )

                continue

            revisados += 1

            for linea, modulo in importaciones(
                arbol,
                paquete,
            ):

                destino = capa_destino(
                    modulo
                )

                if (
                    origen,
                    destino,
                ) in DEPENDENCIAS_A_REVISAR:

                    hallazgos.add((
                        str(ruta),
                        linea,

                        f"{CAPAS[origen]} -> "
                        f"{CAPAS[destino]}",
                    ))

                # Detecta acoplamiento de Business
                # con excepciones del framework HTTP.

                if (
                    origen == "business"

                    and modulo
                    == "fastapi.HTTPException"
                ):

                    hallazgos.add((
                        str(ruta),
                        linea,

                        "Business utiliza "
                        "HTTPException de FastAPI",
                    ))

                # Detecta posibles consultas SQL
                # construidas directamente en Business.
                # No penaliza el uso de Session.

                if (
                    origen == "business"

                    and modulo in {
                        "sqlalchemy.select",
                        "sqlalchemy.text",
                        "sqlalchemy.update",
                        "sqlalchemy.delete",
                        "sqlalchemy.insert",
                    }
                ):

                    hallazgos.add((
                        str(ruta),
                        linea,

                        "Business importa una "
                        "operacion SQLAlchemy",
                    ))

    print(
        f"\nArchivos Python revisados: {revisados}"
    )

    for ruta, linea, mensaje in sorted(
        hallazgos
    ):

        informe.revisar(
            f"{ruta}:{linea} | {mensaje}"
        )

    if not hallazgos:

        print(
            "[OK] No se encontraron dependencias "
            "incluidas en las reglas de revision."
        )

    print(
        "\nNota: las importaciones detectadas "
        "requieren revision arquitectonica. "
        "No todas constituyen necesariamente "
        "una infraccion."
    )


# =======================================
# COMUNICACION HTTP LOCAL
# =======================================

class SinRedirecciones(
    HTTPRedirectHandler
):

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


OPENER = build_opener(
    SinRedirecciones()
)


def solicitar(
    ruta,
    pregunta,
    token=None,
    consentimiento=None,
):

    cuerpo = {
        "pregunta": pregunta,
    }

    if consentimiento is not None:

        cuerpo[
            "autorizo_envio_ia"
        ] = consentimiento

    headers = {
        "Content-Type": "application/json",

        "Accept": "application/json",
    }

    if token:

        headers["Authorization"] = (
            f"Bearer {token}"
        )

    solicitud = Request(
        BASE + ruta,

        data=json.dumps(
            cuerpo,
            ensure_ascii=False,
        ).encode("utf-8"),

        headers=headers,

        method="POST",
    )

    inicio = time.perf_counter()

    try:

        with OPENER.open(
            solicitud,
            timeout=60,
        ) as respuesta:

            estado = respuesta.status

            datos = json.loads(
                respuesta.read().decode(
                    "utf-8"
                )
            )

        if not isinstance(
            datos,
            dict,
        ):

            datos = None

    except HTTPError as error:

        estado = error.code

        datos = None

        error.close()

    except (
        URLError,
        TimeoutError,
        OSError,
        ValueError,
    ):

        estado = 0

        datos = None

    duracion = (
        time.perf_counter()
        - inicio
    )

    return (
        estado,
        datos,
        duracion,
    )


# =======================================
# VALIDACION FINANCIERA
# =======================================

def decimal(valor):

    numero = Decimal(
        str(valor)
    )

    if not numero.is_finite():

        raise ValueError(
            "Numero no finito"
        )

    return numero


def sumar(filas, campo):

    return sum(
        (
            decimal(fila[campo])

            for fila in filas
        ),

        CERO,
    )


def porcentaje(parte, total):

    return (
        decimal(parte)
        / decimal(total)
        * Decimal("100")
    ).quantize(
        CENTAVO,

        rounding=ROUND_HALF_UP,
    )


def verificar_cuentas(
    contexto,
    informe,
):

    filas = contexto[
        "postgresql"
    ]["cuentas"]

    resumen = contexto[
        "analisis_financiero"
    ]["cuentas"]

    informe.comprobar(
        "Cantidad de cuentas",

        len(filas)
        == resumen[
            "numero_cuentas_activas"
        ],
    )

    real = sumar(
        filas,
        "saldo_real",
    )

    reservado = sumar(
        filas,
        "reservado",
    )

    libre = sumar(
        filas,
        "saldo_libre",
    )

    informe.comprobar(
        "Total saldo real",

        real == decimal(
            resumen["saldo_real_total"]
        ),
    )

    informe.comprobar(
        "Total reservado",

        reservado == decimal(
            resumen["reservado_total"]
        ),
    )

    informe.comprobar(
        "Total saldo libre",

        libre == decimal(
            resumen["saldo_libre_total"]
        ),
    )

    informe.comprobar(
        "Ecuacion financiera real - reservado = libre",

        real - reservado == libre,
    )

    informe.comprobar(
        "Ecuacion correcta en cada cuenta",

        all(
            (
                decimal(fila["saldo_real"])

                - decimal(fila["reservado"])
            )

            == decimal(
                fila["saldo_libre"]
            )

            for fila in filas
        ),
    )


def verificar_obligaciones(
    contexto,
    informe,
):

    filas = contexto[
        "postgresql"
    ]["obligaciones"]

    resumen = contexto[
        "analisis_financiero"
    ]["obligaciones"]

    informe.comprobar(
        "Cantidad total de obligaciones",

        len(filas)
        == resumen[
            "obligaciones_totales"
        ],
    )

    configuraciones = [

        (
            "POR_PAGAR",
            "ACTIVA",

            "deudas_propias_activas",

            "monto_pendiente_por_pagar",
        ),

        (
            "POR_COBRAR",
            "ACTIVA",

            "cobros_activos",

            "monto_pendiente_por_cobrar",
        ),

        (
            "POR_PAGAR",
            "SALDADA",

            "deudas_propias_saldadas",

            None,
        ),

        (
            "POR_COBRAR",
            "SALDADA",

            "cobros_saldados",

            None,
        ),
    ]

    for tipo, estado, conteo, importe in (
        configuraciones
    ):

        seleccion = [
            fila

            for fila in filas

            if fila["tipo"] == tipo

            and fila["estado"] == estado
        ]

        informe.comprobar(
            f"Conteo {conteo}",

            len(seleccion)
            == resumen[conteo],
        )

        if importe:

            informe.comprobar(
                f"Total {importe}",

                sumar(
                    seleccion,
                    "pendiente",
                )

                == decimal(
                    resumen[importe]
                ),
            )

    informe.comprobar(
        "Obligaciones saldadas sin saldo pendiente",

        all(
            decimal(fila["pendiente"])
            == CERO

            for fila in filas

            if fila["estado"] == "SALDADA"
        ),
    )


def verificar_reservas(
    contexto,
    informe,
):

    reservas = contexto[
        "analisis_financiero"
    ]["reservas"]

    relaciones = reservas[
        "relaciones_meta_cuenta"
    ]

    total = sumar(
        relaciones,
        "reservado_neto",
    )

    informe.comprobar(
        "Total de reservas vinculadas",

        total == decimal(
            reservas[
                "total_reservado_vinculado"
            ]
        ),
    )

    pares = {
        (
            fila["id_meta"],
            fila["id_cuenta"],
        )

        for fila in relaciones
    }

    informe.comprobar(
        "Relaciones meta-cuenta sin duplicados",

        len(pares) == len(relaciones),
    )

    informe.comprobar(
        "Cantidad de relaciones",

        len(relaciones)

        == reservas[
            "numero_relaciones_meta_cuenta"
        ],
    )

    metas = {
        fila["id_meta"]

        for fila in relaciones
    }

    informe.comprobar(
        "Cantidad de metas con reserva",

        len(metas)

        == reservas[
            "numero_metas_con_reserva"
        ],
    )

    informe.comprobar(
        "Reservas netas positivas",

        all(
            decimal(
                fila["reservado_neto"]
            ) > CERO

            for fila in relaciones
        ),
    )

    por_cuenta = defaultdict(
        lambda: CERO
    )

    for fila in relaciones:

        por_cuenta[
            fila["id_cuenta"]
        ] += decimal(
            fila["reservado_neto"]
        )

    cuentas = contexto[
        "postgresql"
    ].get(
        "cuentas", []
    )

    if "cuentas" in contexto[
        "postgresql"
    ]:

        ids = {
            fila["id_cuenta"]

            for fila in cuentas
        }

        if not set(
            por_cuenta
        ).issubset(ids):

            informe.revisar(
                "Hay reservas vinculadas a cuentas "
                "no incluidas en el listado activo. "
                "Revisar estados y alcance."
            )

        informe.comprobar(
            "Reservas por cuenta activa consistentes",

            all(
                decimal(fila["reservado"])

                == por_cuenta[
                    fila["id_cuenta"]
                ]

                for fila in cuentas
            ),
        )


def verificar_metas(
    contexto,
    informe,
):

    metas = contexto[
        "postgresql"
    ]["metas"]

    for indice, meta in enumerate(
        metas,
        start=1,
    ):

        objetivo = decimal(
            meta["objetivo"]
        )

        informe.comprobar(
            f"Meta {indice}: objetivo positivo",

            objetivo > CERO,
        )

        if objetivo > CERO:

            esperado = porcentaje(
                meta["acumulado"],
                objetivo,
            )

            informe.comprobar(
                f"Meta {indice}: progreso",

                esperado == decimal(
                    meta[
                        "progreso_porcentaje"
                    ]
                ),
            )


def verificar_presupuestos(
    contexto,
    informe,
):

    filas = contexto[
        "postgresql"
    ]["presupuestos"]

    for indice, fila in enumerate(
        filas,
        start=1,
    ):

        limite = decimal(
            fila["limite"]
        )

        gastado = decimal(
            fila["gastado"]
        )

        informe.comprobar(
            f"Presupuesto {indice}: disponible",

            limite - gastado

            == decimal(
                fila["disponible"]
            ),
        )

        informe.comprobar(
            f"Presupuesto {indice}: limite positivo",

            limite > CERO,
        )

        if limite > CERO:

            esperado = porcentaje(
                gastado,
                limite,
            )

            informe.comprobar(
                f"Presupuesto {indice}: porcentaje",

                esperado == decimal(
                    fila["porcentaje_usado"]
                ),
            )


def verificar_gmf(
    contexto,
    informe,
):

    sql = contexto[
        "postgresql"
    ]

    resumen = sql[
        "resumen_mensual"
    ]

    categorias = sql[
        "gastos_por_categoria"
    ]

    total_categorias = sumar(
        categorias,
        "total_incluido_gmf",
    )

    gastos = decimal(
        resumen["gastos_ordinarios"]
    )

    gmf = decimal(
        resumen["gmf_total"]
    )

    diferencia = (
        total_categorias - gastos
    )

    residual = (
        total_categorias
        - gastos
        - gmf
    )

    print("\nConciliacion GMF:")

    print(
        "Categorias menos gastos ordinarios: "
        f"{diferencia} COP"
    )

    print(
        "Categorias menos gastos y GMF total: "
        f"{residual} COP"
    )

    # No se impone una ecuacion incorrecta.
    # El GMF total podria incluir operaciones
    # distintas de los gastos ordinarios.

    informe.revisar(
        "Validar el alcance de GMF total y GMF "
        "por categoria contra las reglas "
        "originales de movimientos."
    )


def verificar_fuseki(
    contexto,
    informe,
):

    rdf = contexto[
        "fuseki"
    ]

    informe.comprobar(
        "Grafo RDF de usuario identificado",

        isinstance(
            rdf.get("grafo"),
            str,
        )

        and rdf["grafo"].startswith(
            "urn:finanzas:grafo:usuario:"
        ),
    )

    informe.comprobar(
        "Fecha de instantanea RDF disponible",

        bool(
            rdf.get("fecha_instantanea")
        ),
    )

    print(
        "Vigencia RDF: "
        f"{rdf.get('vigencia', 'DESCONOCIDA')}"
    )

    controles = rdf.get(
        "comprobaciones", {}
    )

    informe.comprobar(
        "Clasificacion SQL/RDF de obligaciones",

        controles.get(
            "tipos_obligaciones", {}
        ).get(
            "coincide_con_postgresql"
        ) is True,
    )

    informe.comprobar(
        "Relaciones SQL/RDF de reservas",

        controles.get(
            "reservas_meta_cuenta", {}
        ).get(
            "coincide_con_postgresql"
        ) is True,
    )

    if rdf.get("vigencia") != "RECIENTE":

        informe.revisar(
            "Revisar antiguedad de la "
            "instantanea semantica."
        )


def verificar_contexto_general(
    contexto,
    informe,
):

    print("\nCONSISTENCIA FINANCIERA")
    print("-" * 60)

    verificadores = [

        verificar_cuentas,

        verificar_obligaciones,

        verificar_reservas,

        verificar_metas,

        verificar_presupuestos,

        verificar_gmf,

        verificar_fuseki,
    ]

    for verificar in verificadores:

        try:

            verificar(
                contexto,
                informe,
            )

        except (
            KeyError,
            TypeError,
            ValueError,
            ArithmeticError,
        ) as error:

            informe.comprobar(
                (
                    f"{verificar.__name__}: "
                    f"estructura no valida "
                    f"({type(error).__name__})"
                ),

                False,
            )


# =======================================
# RENDIMIENTO Y RESPUESTAS REALES
# =======================================

def dinero_formateado(valor):

    numero = decimal(
        valor
    )

    if numero == numero.to_integral_value():

        numero = numero.to_integral_value()

    texto = format(
        numero,
        ",f",
    ).translate(
        str.maketrans({
            ",": ".",
            ".": ",",
        })
    )

    return f"${texto} COP"


def verificar_respuesta(
    escenario,
    datos,
    contexto,
    informe,
):

    metodo = datos.get(
        "metodo"
    )

    texto = datos.get(
        "respuesta", ""
    )

    if not informe.comprobar(
        f"{escenario}: respuesta no vacia",

        isinstance(texto, str)

        and bool(texto.strip()),
    ):

        return

    informe.comprobar(
        f"{escenario}: metodo reconocido",

        metodo in {
            "RAG_SQL_SPARQL",
            "CALCULO_SQL_RESPALDO",
        },
    )

    if metodo == "CALCULO_SQL_RESPALDO":

        informe.comprobar(
            f"{escenario}: respaldo identificado",

            datos.get("modelo") is None

            and datos.get("proveedor")
            == "FastAPI/PostgreSQL",
        )

    elif metodo == "RAG_SQL_SPARQL":

        informe.comprobar(
            f"{escenario}: modelo identificado",

            bool(datos.get("modelo")),
        )

    print(
        f"Metodo: {metodo}"
    )

    print(
        f"Longitud respuesta: {len(texto)} caracteres"
    )

    analisis = contexto.get(
        "analisis_financiero", {}
    )

    try:

        if escenario == "saldo":

            esperado = dinero_formateado(
                analisis["cuentas"][
                    "saldo_libre_total"
                ]
            )

            informe.comprobar(
                "Saldo mostrado coincide con contexto",

                esperado in texto,
            )

        elif escenario == "obligaciones":

            resumen = analisis[
                "obligaciones"
            ]

            importe = dinero_formateado(
                resumen[
                    "monto_pendiente_por_cobrar"
                ]
            )

            conteo = resumen[
                "deudas_propias_saldadas"
            ]

            informe.comprobar(
                "Importe por cobrar correcto",

                importe in texto,
            )

            informe.comprobar(
                "Conteo de deudas saldadas correcto",

                (
                    f"Deudas propias saldadas: {conteo}"
                ) in texto,
            )

        elif escenario == "reservas":

            importe = dinero_formateado(
                analisis["reservas"][
                    "total_reservado_vinculado"
                ]
            )

            informe.comprobar(
                "Total de reservas correcto",

                importe in texto,
            )

        elif escenario == "general":

            titulos = (

                "Cuentas y liquidez",

                "Ingresos y gastos",

                "Deudas y dinero por cobrar",

                "Presupuestos",

                "Metas financieras",

                "Reservas y distribución por metas",
            )

            informe.comprobar(
                "Cobertura de dominios financieros",

                all(
                    titulo in texto

                    for titulo in titulos
                ),
            )

    except (
        KeyError,
        TypeError,
        ValueError,
        ArithmeticError,
    ):

        informe.comprobar(
            f"{escenario}: contexto comparable",

            False,
        )


def auditar_api(
    token,
    muestras,
    usar_ia,
    informe,
):

    print("\nAUDITORIA API LOCAL")
    print("-" * 60)

    estado, _, _ = solicitar(
        "/contexto",

        ESCENARIOS["saldo"],
    )

    informe.comprobar(
        "API sin autenticacion rechazada",

        estado in {401, 403},
    )

    estado, _, _ = solicitar(
        "/preguntar",

        ESCENARIOS["saldo"],

        token=token,

        consentimiento=False,
    )

    if estado == 401:

        informe.comprobar(
            "JWT de auditoria vigente",

            False,
        )

        return

    informe.comprobar(
        "API sin consentimiento rechazada",

        estado == 403,
    )

    for escenario, pregunta in (
        ESCENARIOS.items()
    ):

        print(
            f"\nESCENARIO: {escenario}"
        )

        tiempos = []

        ultimo_contexto = None

        for indice in range(
            1,
            muestras + 1,
        ):

            estado, datos, segundos = (
                solicitar(
                    "/contexto",

                    pregunta,

                    token=token,
                )
            )

            tiempos.append(
                segundos
            )

            print(
                f"Contexto {indice}: "
                f"HTTP {estado} | "
                f"{segundos:.3f} s"
            )

            valido = informe.comprobar(
                "Contexto recuperado",

                estado == 200

                and datos is not None,
            )

            if valido:

                ultimo_contexto = datos

        print(
            "Mediana contexto: "
            f"{statistics.median(tiempos):.3f} s"
        )

        print(
            "Maximo contexto: "
            f"{max(tiempos):.3f} s"
        )

        if ultimo_contexto is None:

            informe.revisar(
                "No hay contexto valido "
                "para continuar este escenario."
            )

            continue

        if escenario == "general":

            verificar_contexto_general(
                ultimo_contexto,
                informe,
            )

        if usar_ia:

            estado, datos, segundos = (
                solicitar(
                    "/preguntar",

                    pregunta,

                    token=token,

                    consentimiento=True,
                )
            )

            print(
                f"Respuesta asistente: "
                f"HTTP {estado} | "
                f"{segundos:.3f} s"
            )

            valido = informe.comprobar(
                "Respuesta asistente recuperada",

                estado == 200

                and datos is not None,
            )

            if valido:

                verificar_respuesta(
                    escenario,

                    datos,

                    ultimo_contexto,

                    informe,
                )

            # Evita llamadas consecutivas
            # inmediatas al proveedor.
            if escenario != "general":

                time.sleep(15)


# =======================================
# EJECUCION
# =======================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Auditoria del asistente "
            "financiero 27.8"
        ),
    )

    parser.add_argument(
        "--arquitectura",

        action="store_true",

        help=(
            "Solo revisar dependencias "
            "entre capas."
        ),
    )

    parser.add_argument(
        "--muestras",

        type=int,

        default=3,

        choices=range(1, 11),

        metavar="N",

        help=(
            "Solicitudes de contexto "
            "por escenario: 1 a 10."
        ),
    )

    parser.add_argument(
        "--ia",

        action="store_true",

        help=(
            "Realizar tambien una consulta "
            "al asistente por escenario."
        ),
    )

    args = parser.parse_args()

    informe = Informe()

    auditar_arquitectura(
        informe
    )

    if not args.arquitectura:

        token = getpass.getpass(
            "\nJWT local, sin compartirlo "
            "con terceros: "
        ).strip()

        if token.lower().startswith(
            "bearer "
        ):

            token = token[7:].strip()

        if not token:

            print(
                "No se proporciono un JWT."
            )

            return 1

        auditar_api(
            token,

            args.muestras,

            args.ia,

            informe,
        )

    informe.resumen()

    return (
        1
        if informe.fallos
        else 0
    )


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
