"""Auditoria estatica de arquitectura.

Paso 28.2 D.

No importa app ni abre conexiones externas.
"""

import ast
import re
import sys

from pathlib import Path
from importlib.util import resolve_name


REGLAS = {
    "presentation": {
        "presentation",
        "business",
        "schemas",
    },
    "business": {
        "business",
        "services",
        "persistence",
        "models",
        "schemas",
    },
    "services": {
        "services",
        "persistence",
    },
    "persistence": {
        "persistence",
        "models",
        "base",
    },
    "models": {
        "models",
        "base",
    },
    "schemas": {"schemas"},
    "base": {"base"},
    "root": {"root"},
    "composition": {
        "presentation",
        "business",
        "persistence",
    },
}


SQL = {
    "select",
    "text",
    "insert",
    "update",
    "delete",
    "create_engine",
    "create_async_engine",
    "sessionmaker",
    "async_sessionmaker",
}


METODOS = {
    "execute",
    "exec_driver_sql",
    "scalar",
    "scalars",
    "query",
    "get",
    "get_one",
    "refresh",
    "connection",
    "connect",
    "begin",
    "begin_nested",
    "add",
    "add_all",
    "delete",
    "merge",
    "bulk_save_objects",
    "bulk_insert_mappings",
    "bulk_update_mappings",
}


TRANSACCION = {
    "commit",
    "rollback",
    "flush",
}


# ========================================
# IDENTIFICACION DE CAPAS
# ========================================

def capa(modulo):

    if modulo == "app":
        return "root"

    if (
        modulo == "app.main"
        or modulo.startswith("app.main.")
    ):
        return "composition"

    if (
        modulo == "app.dependencies"
        or modulo.startswith("app.dependencies.")
    ):
        return "presentation"

    partes = modulo.split(".")

    if len(partes) < 2 or partes[0] != "app":
        return None

    return {
        "routers": "presentation",
        "database": "base",
        "models": "models",
        "schemas": "schemas",
        "business": "business",
        "services": "services",
        "persistence": "persistence",
    }.get(partes[1], "desconocida")


def permitido(origen, destino):

    # Excepcion tecnica limitada:
    # inyeccion de sesiones y tipo Usuario.

    if origen == "app.dependencies" and destino in {
        "app.models.Usuario",
        "app.persistence.database.get_db",
    }:

        return True

    # Composicion de los eventos SQLAlchemy.

    if (
        origen == "app.main"
        and destino.startswith("app.persistence.")
    ):

        return (
            destino
            == "app.persistence.database.SesionFinanciera"
        )

    return capa(destino) in REGLAS.get(
        capa(origen),
        set(),
    )


def nombre(nodo):

    if isinstance(nodo, ast.Name):
        return nodo.id

    if isinstance(nodo, ast.Attribute):

        base = nombre(nodo.value)

        return base + "." + nodo.attr if base else ""

    return ""


# ========================================
# ANALISIS ESTATICO
# ========================================

def analizar(modulo, codigo, paquete):

    arbol = ast.parse(codigo)

    origen = capa(modulo)

    errores = set()

    alias = {}

    sesiones = {
        "db",
        "session",
        "sesion",
        "engine",
        "connection",
        "conn",
        "conexion",
    }

    def fallo(nodo, razon):

        errores.add(
            (nodo.lineno, razon)
        )

    if origen not in REGLAS:

        errores.add(
            (1, "Modulo sin capa asignada")
        )

    # Analizar importaciones absolutas,
    # relativas y alias.

    for nodo in ast.walk(arbol):

        pares = []

        if isinstance(nodo, ast.Import):

            for a in nodo.names:

                alias[
                    a.asname or a.name.split(".")[0]
                ] = (
                    a.name
                    if a.asname
                    else a.name.split(".")[0]
                )

                pares.append(a.name)

        elif isinstance(nodo, ast.ImportFrom):

            base = nodo.module or ""

            if nodo.level:

                try:

                    base = resolve_name(
                        "." * nodo.level + base,
                        paquete,
                    )

                except ImportError:

                    fallo(
                        nodo,
                        "Importacion relativa no resuelta",
                    )

                    continue

            for a in nodo.names:

                destino = base + "." + a.name

                alias[a.asname or a.name] = destino

                pares.append(destino)

                if a.name == "*":

                    fallo(
                        nodo,
                        "Importacion comodin no auditable",
                    )

        for destino in pares:

            if (
                destino == "app"
                or destino.startswith("app.")
            ):

                if not permitido(modulo, destino):

                    fallo(
                        nodo,
                        "Dependencia prohibida: "
                        + destino,
                    )

            if origen in {
                "business",
                "services",
                "persistence",
                "models",
                "schemas",
                "base",
            } and destino.split(".")[0] in {
                "fastapi",
                "starlette",
            }:

                fallo(
                    nodo,
                    "Dependencia HTTP fuera de Presentation: "
                    + destino,
                )

            if (
                origen in {
                    "business",
                    "services",
                    "presentation",
                    "composition",
                }
                and destino.startswith("sqlalchemy.")
                and destino.split(".")[-1] in SQL
            ):

                fallo(
                    nodo,
                    "Constructor de persistencia: "
                    + destino,
                )

    def resolver(nodo):

        bruto = nombre(nodo)

        inicio, sep, resto = bruto.partition(".")

        return alias.get(inicio, inicio) + (
            sep + resto if sep else ""
        )

    # Detectar parametros que representan
    # sesiones o conexiones SQLAlchemy.

    for nodo in ast.walk(arbol):

        if (
            isinstance(nodo, ast.arg)
            and nodo.annotation
            and any(
                x in nombre(nodo.annotation)
                for x in (
                    "Session",
                    "SesionBD",
                    "Connection",
                    "Engine",
                )
            )
        ):

            sesiones.add(nodo.arg)

    # Propagar alias simples de una sesion.

    cambio = True

    while cambio:

        cambio = False

        for nodo in ast.walk(arbol):

            if (
                isinstance(nodo, ast.Assign)
                and isinstance(nodo.value, ast.Name)
                and nodo.value.id in sesiones
            ):

                for destino in nodo.targets:

                    if (
                        isinstance(destino, ast.Name)
                        and destino.id not in sesiones
                    ):

                        sesiones.add(destino.id)

                        cambio = True

    # Analizar llamadas y operaciones.

    for nodo in ast.walk(arbol):

        if isinstance(nodo, ast.Call):

            destino = resolver(nodo.func)

            if destino in {
                "__import__",
                "builtins.__import__",
                "importlib.import_module",
            }:

                fallo(
                    nodo,
                    "Importacion dinamica: revisar explicitamente",
                )

            if origen in {
                "presentation",
                "business",
                "services",
                "composition",
            }:

                if (
                    destino.startswith("sqlalchemy.")
                    and destino.split(".")[-1] in SQL
                ):

                    fallo(
                        nodo,
                        "Construccion SQL directa: "
                        + destino,
                    )

                if (
                    isinstance(nodo.func, ast.Attribute)
                    and isinstance(
                        nodo.func.value,
                        ast.Name,
                    )
                    and nodo.func.value.id in sesiones
                ):

                    metodo = nodo.func.attr

                    if (
                        metodo in METODOS
                        or (
                            metodo in TRANSACCION
                            and origen != "business"
                        )
                    ):

                        fallo(
                            nodo,
                            "Operacion directa de persistencia: "
                            + nombre(nodo.func),
                        )

            if (
                origen in {
                    "presentation",
                    "business",
                    "services",
                    "composition",
                }
                and destino in {
                    "urllib.request.urlopen",
                    "requests.get",
                    "requests.post",
                    "requests.put",
                    "requests.delete",
                    "httpx.get",
                    "httpx.post",
                    "httpx.put",
                    "httpx.delete",
                }
            ):

                if origen != "services":

                    fallo(
                        nodo,
                        "Transporte HTTP fuera de Services/Persistence: "
                        + destino,
                    )

        # Detectar posibles sentencias SPARQL
        # fuera de la capa de persistencia.

        if (
            origen in {
                "presentation",
                "business",
                "services",
            }
            and isinstance(nodo, ast.Constant)
            and isinstance(nodo.value, str)
        ):

            if re.search(
                r"\b(?:SELECT\b[\s\S]{0,2000}\bWHERE\s*\{"
                r"|INSERT\s+DATA\s*\{"
                r"|DELETE\s+DATA\s*\{"
                r"|DROP\s+GRAPH\b)",
                nodo.value,
                re.I,
            ):

                fallo(
                    nodo,
                    "Posible sentencia SPARQL fuera de Persistence",
                )

    return sorted(errores)


# ========================================
# AUDITORIA DE TODOS LOS MODULOS
# ========================================

def auditar(raiz):

    hallazgos = []

    cantidad = 0

    for ruta in sorted(
        (raiz / "app").rglob("*.py")
    ):

        rel = ruta.relative_to(raiz)

        # Las pruebas pueden acceder a varias capas.
        # No forman parte del codigo de produccion.

        if rel.parts[1] == "tests":
            continue

        cantidad += 1

        partes = list(
            rel.with_suffix("").parts
        )

        if partes[-1] == "__init__":

            partes.pop()

            paquete = ".".join(partes)

        else:

            paquete = ".".join(partes[:-1])

        modulo = ".".join(partes)

        try:

            codigo = ruta.read_text(
                encoding="utf-8-sig"
            )

            for linea, razon in analizar(
                modulo,
                codigo,
                paquete,
            ):

                hallazgos.append(
                    (
                        str(rel),
                        linea,
                        razon,
                    )
                )

        except (SyntaxError, UnicodeError) as exc:

            hallazgos.append(
                (
                    str(rel),
                    getattr(exc, "lineno", 1) or 1,
                    "Codigo no analizable",
                )
            )

    # Impedir la reaparicion de modulos retirados.

    for antiguo in (
        "services/fuseki_client.py",
        "services/semantica_auto_sync.py",
        "services/rag_retrieval_service.py",
        "business/rag_intencion.py",
        "business/rag_motor_respuestas.py",
        "business/rag_respuestas_directas.py",
    ):

        if (raiz / "app" / antiguo).exists():

            hallazgos.append(
                (
                    "app/" + antiguo,
                    1,
                    "Modulo retirado presente",
                )
            )

    if not cantidad:

        hallazgos.append(
            (
                "app",
                1,
                "No se encontraron modulos",
            )
        )

    return cantidad, hallazgos


# ========================================
# AUTOPRUEBAS DEL AUDITOR
# ========================================

def autoprueba():

    casos = [
        (
            "app.routers.x",
            "from app.services import auth_service",
            True,
        ),
        (
            "app.business.x",
            "from fastapi import HTTPException",
            True,
        ),
        (
            "app.services.x",
            "from app.business import errores",
            True,
        ),
        (
            "app.persistence.x",
            "from app.services import auth_service",
            True,
        ),
        (
            "app.business.x",
            "from sqlalchemy import select as s\ns(X)",
            True,
        ),
        (
            "app.business.x",
            "def f(db):\n    db.get(X,1)",
            True,
        ),
        (
            "app.business.x",
            "def f(db):\n    s=db\n    s.refresh(x)",
            True,
        ),
        (
            "app.business.x",
            "def f(db):\n"
            "    db.commit()\n"
            "    db.rollback()\n"
            "    db.flush()",
            False,
        ),
        (
            "app.dependencies",
            "from app.persistence.database import get_db",
            False,
        ),
        (
            "app.dependencies",
            "from app.persistence.database import engine",
            True,
        ),
        (
            "app.business.x",
            "from app.persistence import usuario_repository",
            False,
        ),
        (
            "app.routers.x",
            "from ..services import auth_service",
            True,
        ),
        (
            "app.business.x",
            "from sqlalchemy import select",
            True,
        ),
        (
            "app.routers.x",
            'q="SELECT ?s WHERE { ?s ?p ?o }"',
            True,
        ),
        (
            "app.persistence.x",
            "from sqlalchemy import select\nselect(X)",
            False,
        ),
        (
            "app.models.x",
            "from app.database.base import Base",
            False,
        ),
    ]

    for modulo, codigo, esperado in casos:

        resultado = analizar(
            modulo,
            codigo,
            modulo.rpartition(".")[0],
        )

        assert bool(resultado) == esperado, (
            modulo,
            codigo,
        )

    print(
        "AUTOPRUEBAS:",
        len(casos),
        "correctas",
    )


# ========================================
# EJECUCION PRINCIPAL
# ========================================

def main():

    autoprueba()

    raiz = Path(__file__).resolve().parent

    cantidad, hallazgos = auditar(raiz)

    print(
        "MODULOS DE PRODUCCION:",
        cantidad,
    )

    for ruta, linea, razon in hallazgos:

        print(
            f"{ruta}:{linea}: {razon}"
        )

    print(
        "HALLAZGOS:",
        len(hallazgos),
    )

    return int(bool(hallazgos))


if __name__ == "__main__":

    sys.exit(main())