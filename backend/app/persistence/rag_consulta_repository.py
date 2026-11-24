"""Consultas financieras dinámicas. Persistence.

Solo SELECT parametrizados.
No importa Business ni Services.
"""

from decimal import Decimal

from sqlalchemy import (
    and_,
    case,
    func,
    or_,
    select,
    union_all,
)

from sqlalchemy.orm import aliased

from app.models import (
    AporteMeta,
    CategoriaMovimiento,
    CuentaFinanciera,
    MetaFinanciera,
    Movimiento,
    ObligacionFinanciera,
    Presupuesto,
    Transferencia,
)


def _validar_usuario(usuario):

    if type(usuario) is not int or usuario <= 0:
        raise ValueError("Usuario inválido")


def _categoria_autorizada(categoria, usuario):

    return or_(
        categoria.id_usuario == usuario,
        and_(
            categoria.id_usuario.is_(None),
            categoria.es_sistema.is_(True),
        ),
    )


def _reservas(usuario):

    a = AporteMeta
    c = CuentaFinanciera
    m = MetaFinanciera

    neto = func.sum(
        case(
            (a.tipo == "RESERVA", a.monto),
            else_=-a.monto,
        )
    )

    return (
        select(
            a.id_meta.label("_id"),
            a.id_cuenta.label("_id2"),
            m.nombre_meta.label("meta"),
            c.nombre_cuenta.label("cuenta"),
            neto.label("reservado_neto"),
        )
        .select_from(a)
        .join(c, c.id_cuenta == a.id_cuenta)
        .join(m, m.id_meta == a.id_meta)
        .where(
            a.id_usuario == usuario,
            c.id_usuario == usuario,
            m.id_usuario == usuario,
            a.estado == "ACTIVO",
        )
        .group_by(
            a.id_meta,
            a.id_cuenta,
            m.nombre_meta,
            c.nombre_cuenta,
        )
    )


def _cuentas(usuario):

    c = CuentaFinanciera
    m = Movimiento

    efecto = case(
        (m.tipo == "INGRESO", m.monto),
        (
            m.tipo == "GASTO",
            -m.monto - m.monto_gmf,
        ),
        else_=0,
    )

    movimientos = (
        select(
            m.id_cuenta.label("cuenta_id"),
            func.sum(efecto).label("variacion"),
        )
        .select_from(m)
        .join(c, c.id_cuenta == m.id_cuenta)
        .where(
            c.id_usuario == usuario,
            m.estado == "ACTIVO",
        )
        .group_by(m.id_cuenta)
        .subquery()
    )

    pares = _reservas(usuario).subquery()

    reservas = (
        select(
            pares.c._id2.label("cuenta_id"),
            func.sum(
                pares.c.reservado_neto
            ).label("total"),
        )
        .group_by(pares.c._id2)
        .subquery()
    )

    real = (
        c.saldo_inicial
        + func.coalesce(movimientos.c.variacion, 0)
    )

    reservado = func.coalesce(
        reservas.c.total, 0
    )

    return (
        select(
            c.id_cuenta.label("_id"),
            c.nombre_cuenta.label("nombre"),
            c.tipo_cuenta.label("tipo"),
            c.estado.label("estado"),
            real.label("saldo_real"),
            reservado.label("reservado"),
            (real - reservado).label("saldo_libre"),
        )
        .select_from(c)
        .outerjoin(
            movimientos,
            movimientos.c.cuenta_id == c.id_cuenta,
        )
        .outerjoin(
            reservas,
            reservas.c.cuenta_id == c.id_cuenta,
        )
        .where(c.id_usuario == usuario)
    )


def _movimientos(usuario):

    m = Movimiento
    c = CuentaFinanciera
    cat = CategoriaMovimiento
    ob = ObligacionFinanciera

    return (
        select(
            m.id_movimiento.label("_id"),
            m.fecha_movimiento.label("fecha"),
            m.tipo.label("tipo"),
            m.origen.label("origen"),
            m.estado.label("estado"),
            c.nombre_cuenta.label("cuenta"),
            c.tipo_cuenta.label("tipo_cuenta"),
            func.coalesce(
                cat.nombre_categoria,
                "Sin categoría",
            ).label("categoria"),
            ob.nombre_obligacion.label("obligacion"),
            m.monto.label("monto"),
            m.monto_gmf.label("gmf"),
            (
                m.monto + m.monto_gmf
            ).label("monto_con_gmf"),
        )
        .select_from(m)
        .join(c, c.id_cuenta == m.id_cuenta)
        .outerjoin(
            cat,
            and_(
                cat.id_categoria == m.id_categoria,
                _categoria_autorizada(cat, usuario),
            ),
        )
        .outerjoin(
            ob,
            and_(
                ob.id_obligacion == m.id_obligacion,
                ob.id_usuario == usuario,
            ),
        )
        .where(c.id_usuario == usuario)
    )


def _obligaciones(usuario):

    ob = ObligacionFinanciera
    m = Movimiento
    c = CuentaFinanciera

    abonado = (
        select(
            func.coalesce(func.sum(m.monto), 0)
        )
        .select_from(m)
        .join(c, c.id_cuenta == m.id_cuenta)
        .where(
            c.id_usuario == usuario,
            m.id_obligacion == ob.id_obligacion,
            m.origen == "OBLIGACION",
            m.estado == "ACTIVO",
            or_(
                and_(
                    ob.tipo_obligacion == "POR_PAGAR",
                    m.tipo == "GASTO",
                ),
                and_(
                    ob.tipo_obligacion == "POR_COBRAR",
                    m.tipo == "INGRESO",
                ),
            ),
        )
        .correlate(ob)
        .scalar_subquery()
    )

    return (
        select(
            ob.id_obligacion.label("_id"),
            ob.nombre_obligacion.label("nombre"),
            ob.tipo_obligacion.label("tipo"),
            ob.estado.label("estado"),
            ob.fecha_inicio.label("fecha_inicio"),
            ob.fecha_vencimiento.label("fecha_vencimiento"),
            ob.monto_original.label("monto_original"),
            abonado.label("abonado"),
            (
                ob.monto_original - abonado
            ).label("pendiente"),
        )
        .where(ob.id_usuario == usuario)
    )


def _metas(usuario):

    m = MetaFinanciera

    progreso = func.round(
        m.monto_acumulado
        * 100
        / func.nullif(m.monto_objetivo, 0),
        2,
    )

    return (
        select(
            m.id_meta.label("_id"),
            m.nombre_meta.label("nombre"),
            m.estado.label("estado"),
            m.fecha_objetivo.label("fecha_objetivo"),
            m.monto_objetivo.label("objetivo"),
            m.monto_acumulado.label("acumulado"),
            progreso.label("progreso"),
        )
        .where(m.id_usuario == usuario)
    )


def _presupuestos(usuario):

    p = Presupuesto
    cat = CategoriaMovimiento
    m = Movimiento
    c = CuentaFinanciera

    gastado = (
        select(
            func.coalesce(
                func.sum(m.monto + m.monto_gmf),
                0,
            )
        )
        .select_from(m)
        .join(c, c.id_cuenta == m.id_cuenta)
        .where(
            c.id_usuario == usuario,
            m.id_categoria == p.id_categoria,
            m.tipo == "GASTO",
            m.origen == "NORMAL",
            m.estado == "ACTIVO",
            func.extract(
                "year", m.fecha_movimiento
            ) == p.anio,
            func.extract(
                "month", m.fecha_movimiento
            ) == p.mes,
        )
        .correlate(p)
        .scalar_subquery()
    )

    porcentaje = func.round(
        gastado * 100
        / func.nullif(p.monto_limite, 0),
        2,
    )

    return (
        select(
            p.id_presupuesto.label("_id"),
            cat.nombre_categoria.label("categoria"),
            p.anio.label("anio"),
            p.mes.label("mes"),
            p.monto_limite.label("limite"),
            gastado.label("gastado"),
            (
                p.monto_limite - gastado
            ).label("disponible"),
            porcentaje.label("porcentaje_usado"),
        )
        .select_from(p)
        .join(
            cat,
            cat.id_categoria == p.id_categoria,
        )
        .where(
            p.id_usuario == usuario,
            _categoria_autorizada(cat, usuario),
        )
    )


def _transferencias(usuario):

    t = Transferencia
    m = Movimiento
    c = CuentaFinanciera

    origen = aliased(c)
    destino = aliased(c)

    gmf = (
        select(
            func.coalesce(
                func.sum(m.monto_gmf),
                0,
            )
        )
        .select_from(m)
        .join(c, c.id_cuenta == m.id_cuenta)
        .where(
            c.id_usuario == usuario,
            m.id_transferencia == t.id_transferencia,
            m.tipo == "GASTO",
            m.origen == "TRANSFERENCIA",
            m.estado == "ACTIVO",
        )
        .correlate(t)
        .scalar_subquery()
    )

    return (
        select(
            t.id_transferencia.label("_id"),
            t.fecha_transferencia.label("fecha"),
            origen.nombre_cuenta.label("cuenta_origen"),
            destino.nombre_cuenta.label("cuenta_destino"),
            t.estado.label("estado"),
            t.monto.label("monto"),
            gmf.label("gmf"),
        )
        .select_from(t)
        .join(
            origen,
            origen.id_cuenta == t.id_cuenta_origen,
        )
        .join(
            destino,
            destino.id_cuenta == t.id_cuenta_destino,
        )
        .where(
            origen.id_usuario == usuario,
            destino.id_usuario == usuario,
        )
    )


def _categorias(usuario):

    c = CategoriaMovimiento

    return (
        select(
            c.id_categoria.label("_id"),
            c.nombre_categoria.label("nombre"),
            c.tipo_categoria.label("tipo"),
            c.estado.label("estado"),
        )
        .where(
            _categoria_autorizada(c, usuario)
        )
    )


VISTAS = {
    "cuentas": _cuentas,
    "movimientos": _movimientos,
    "obligaciones": _obligaciones,
    "metas": _metas,
    "presupuestos": _presupuestos,
    "reservas": _reservas,
    "transferencias": _transferencias,
    "categorias": _categorias,
}


def _columna(base, nombre):

    if (
        not isinstance(nombre, str)
        or nombre.startswith("_")
        or nombre not in base.c
    ):
        raise ValueError("Columna no autorizada")

    return base.c[nombre]


def _condicion(columna, operador, valor):

    if operador == "es_nulo":
        return columna.is_(None)

    if operador == "no_nulo":
        return columna.is_not(None)

    if operador == "contiene":

        if not isinstance(valor, str):
            raise ValueError("Filtro textual inválido")

        return func.lower(columna).contains(
            valor.lower(),
            autoescape=True,
        )

    if isinstance(valor, str):

        columna = func.lower(columna)
        valor = valor.lower()

    comparaciones = {
        "igual": lambda: columna == valor,
        "distinto": lambda: columna != valor,
        "mayor": lambda: columna > valor,
        "menor": lambda: columna < valor,
        "mayor_igual": lambda: columna >= valor,
        "menor_igual": lambda: columna <= valor,
    }

    if operador not in comparaciones:
        raise ValueError("Operador no autorizado")

    return comparaciones[operador]()


def construir_select(usuario, plan):
    """Construye exclusivamente una sentencia SELECT."""

    _validar_usuario(usuario)

    constructor = VISTAS.get(plan["entidad"])

    if constructor is None:
        raise ValueError("Vista no autorizada")

    base = constructor(usuario).subquery()

    operacion = plan["operacion"]

    grupos = [
        _columna(base, nombre)
        for nombre in plan["agrupar_por"]
    ]

    condiciones = [
        _condicion(
            _columna(base, filtro["campo"]),
            filtro["operador"],
            filtro["valor"],
        )
        for filtro in plan["filtros"]
    ]

    limite = plan["limite"]

    if type(limite) is not int or not 1 <= limite <= 50:
        raise ValueError("Límite no autorizado")

    if operacion == "listar":

        columnas = [
            _columna(base, nombre)
            for nombre in plan["campos"]
        ]

        if not columnas:
            raise ValueError("Listado sin columnas")

        consulta = select(*columnas).select_from(base)

        ordenables = {
            nombre: _columna(base, nombre)
            for nombre in base.c.keys()
            if not nombre.startswith("_")
        }

    else:

        if operacion == "contar":
            valor = func.count()

        else:

            campo = _columna(base, plan["campo"])

            agregaciones = {
                "sumar": func.sum,
                "promedio": func.avg,
                "minimo": func.min,
                "maximo": func.max,
            }

            if operacion not in agregaciones:
                raise ValueError("Agregación no autorizada")

            valor = agregaciones[operacion](campo)

            if operacion == "sumar":
                valor = func.coalesce(
                    valor, Decimal("0.00")
                )

        valor = valor.label("valor")
        cantidad = func.count().label("cantidad")

        consulta = (
            select(
                *grupos,
                valor,
                cantidad,
            )
            .select_from(base)
        )

        if grupos:
            consulta = consulta.group_by(*grupos)

        ordenables = {
            columna.key: columna
            for columna in grupos
        }

        ordenables.update({
            "valor": valor,
            "cantidad": cantidad,
        })

    if condiciones:
        consulta = consulta.where(*condiciones)

    orden = plan["orden_campo"]

    if orden:

        columna = ordenables.get(orden)

        if columna is None:
            raise ValueError(
                "Ordenamiento no autorizado"
            )

        consulta = consulta.order_by(
            columna.desc().nulls_last()
            if plan["descendente"]
            else columna.asc().nulls_last()
        )

    if operacion == "listar":

        for clave in ("_id", "_id2"):

            if clave in base.c:

                columna = base.c[clave]

                consulta = consulta.order_by(
                    columna.desc()
                    if plan["descendente"]
                    else columna.asc()
                )

    elif grupos:

        consulta = consulta.order_by(
            *grupos
        )

    # El registro adicional detecta truncamiento.
    # Los agregados se calculan antes del límite.

    return consulta.limit(limite + 1)


def ejecutar_consulta_sql(db, usuario, plan):

    consulta = construir_select(
        usuario,
        plan,
    )

    filas = [
        dict(fila)
        for fila in db.execute(
            consulta
        ).mappings().all()
    ]

    limite = plan["limite"]

    return {
        "origen": "PostgreSQL",
        "entidad": plan["entidad"],
        "operacion": plan["operacion"],
        "filas": filas[:limite],
        "truncado": len(filas) > limite,
        "limite": limite,
    }


def obtener_nombres_privados(db, usuario):

    _validar_usuario(usuario)

    c = CuentaFinanciera
    m = MetaFinanciera
    o = ObligacionFinanciera
    cat = CategoriaMovimiento

    consulta = union_all(
        select(c.nombre_cuenta).where(
            c.id_usuario == usuario
        ),
        select(m.nombre_meta).where(
            m.id_usuario == usuario
        ),
        select(o.nombre_obligacion).where(
            o.id_usuario == usuario
        ),
        select(cat.nombre_categoria).where(
            cat.id_usuario == usuario
        ),
    )

    return [
        nombre
        for nombre in db.scalars(consulta).all()
        if isinstance(nombre, str) and nombre.strip()
    ]