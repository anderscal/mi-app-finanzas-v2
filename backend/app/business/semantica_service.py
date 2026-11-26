
"""Proyección RDF de lectura. PostgreSQL sigue siendo la fuente de verdad."""

from collections import defaultdict
from datetime import datetime, time, timezone
from decimal import Decimal

from app.business.errores import CodigoError, ErrorNegocio
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import XSD
from sqlalchemy.orm import Session

from app.persistence import semantica_exportacion_repository as exportacion
from app.persistence.cuenta_repository import obtener_cuentas_con_saldo

FIN = Namespace(
    'http://www.semanticweb.org/user/ontologies/2026/8/untitled-ontology-20/'
)
OP = Namespace('https://datos.finanzas.local/vocab/')
BASE_RECURSOS = 'https://datos.finanzas.local/usuario/'
CERO = Decimal('0.00')


def iri_grafo(id_usuario: int) -> str:
    if type(id_usuario) is not int or id_usuario <= 0:
        raise ValueError('ID de usuario inválido')
    return f'urn:finanzas:grafo:usuario:{id_usuario}'


def _recurso(id_usuario: int, tipo: str, identificador: int) -> URIRef:
    return URIRef(f'{BASE_RECURSOS}{id_usuario}/{tipo}/{identificador}')


def _dinero(valor) -> Literal:
    return Literal(Decimal(valor), datatype=XSD.decimal)


def _texto(valor) -> Literal:
    return Literal(str(valor), datatype=XSD.string)


def _fecha(valor) -> Literal:
    return Literal(datetime.combine(valor, time.min).isoformat(), datatype=XSD.dateTime)


def construir_grafo_usuario(db: Session, id_usuario: int) -> tuple[Graph, dict]:
    """Extrae solamente filas propias del usuario autenticado.

    No hace commit ni escribe en PostgreSQL.
    El grafo sustituye una instantánea anterior, no es un diario de eventos.
    """
    nombre_grafo = iri_grafo(id_usuario)
    g = Graph(identifier=URIRef(nombre_grafo))
    g.bind('fin', FIN)
    g.bind('op', OP)
    usuario = _recurso(id_usuario, 'usuario', id_usuario)
    g.add((usuario, RDF.type, FIN.Usuario))
    g.add((usuario, OP.exportadoEn, Literal(
        datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime
    )))

    cuentas = exportacion.obtener_cuentas(db, id_usuario)
    ids_cuentas = {cu.id_cuenta for cu in cuentas}
    saldos = {
        int(fila['id_cuenta']): Decimal(fila['saldo_actual'])
        for fila in obtener_cuentas_con_saldo(db, id_usuario)
    }

    metas = exportacion.obtener_metas(db, id_usuario)
    ids_metas = {meta.id_meta for meta in metas}
    obligaciones = exportacion.obtener_obligaciones(db, id_usuario)
    ids_obligaciones = {ob.id_obligacion for ob in obligaciones}

    aportes = exportacion.obtener_aportes(db, id_usuario)
    reservados = defaultdict(lambda: CERO)
    vinculados = defaultdict(lambda: CERO)
    for aporte in aportes:
        if aporte.id_cuenta not in ids_cuentas or aporte.id_meta not in ids_metas:
            raise ErrorNegocio(CodigoError.CONFLICTO, 'Reserva asociada a cuenta o meta ajena')
        if aporte.estado != 'ACTIVO':
            continue
        if aporte.tipo not in ('RESERVA', 'LIBERACION'):
            raise ErrorNegocio(CodigoError.CONFLICTO, 'Tipo de aporte inconsistente')
        delta = Decimal(aporte.monto)
        if aporte.tipo == 'LIBERACION':
            delta = -delta
        reservados[aporte.id_cuenta] += delta
        vinculados[aporte.id_meta] += delta

    for cuenta in cuentas:
        real = saldos[cuenta.id_cuenta]
        reservado = reservados[cuenta.id_cuenta]
        if reservado < 0 or reservado > real:
            raise ErrorNegocio(CodigoError.CONFLICTO, 'Saldo reservado inconsistente; revisa la cuenta')
        sujeto = _recurso(id_usuario, 'cuenta', cuenta.id_cuenta)
        g.add((usuario, FIN.tieneCuenta, sujeto))
        g.add((sujeto, RDF.type, FIN.CuentaFinanciera))
        g.add((sujeto, OP.idCuenta, Literal(cuenta.id_cuenta, datatype=XSD.integer)))
        g.add((sujeto, FIN.tieneNombreCuenta, _texto(cuenta.nombre_cuenta)))
        g.add((sujeto, OP.tipoCuenta, _texto(cuenta.tipo_cuenta)))
        g.add((sujeto, OP.estado, _texto(cuenta.estado)))
        g.add((sujeto, FIN.tieneSaldoReal, _dinero(real)))
        g.add((sujeto, FIN.tieneMontoReservado, _dinero(reservado)))
        g.add((sujeto, FIN.tieneSaldoLibre, _dinero(real - reservado)))

    categorias = exportacion.obtener_categorias(db, id_usuario)
    ids_categorias = {c.id_categoria for c in categorias}
    for categoria in categorias:
        sujeto = _recurso(id_usuario, 'categoria', categoria.id_categoria)
        if categoria.tipo_categoria == 'GASTO':
            clase = FIN.CategoriaGasto
        elif categoria.tipo_categoria == 'INGRESO':
            clase = FIN.CategoriaIngreso
        else:
            raise ErrorNegocio(CodigoError.CONFLICTO, 'Tipo de categoría inconsistente')
        g.add((sujeto, RDF.type, clase))
        g.add((sujeto, FIN.tieneNombreCategoria, _texto(categoria.nombre_categoria)))
        g.add((sujeto, OP.estado, _texto(categoria.estado)))

    movimientos = exportacion.obtener_movimientos(db, id_usuario)
    for movimiento in movimientos:
        sujeto = _recurso(id_usuario, 'movimiento', movimiento.id_movimiento)
        if movimiento.origen == 'NORMAL':
            clase = FIN.Gasto if movimiento.tipo == 'GASTO' else FIN.Ingreso
        else:
            clase = FIN.MovimientoFinanciero
        g.add((sujeto, RDF.type, clase))
        g.add((sujeto, FIN.perteneceACuenta, _recurso(
            id_usuario, 'cuenta', movimiento.id_cuenta
        )))
        if movimiento.id_categoria is not None:
            if movimiento.id_categoria not in ids_categorias:
                raise ErrorNegocio(CodigoError.CONFLICTO, 'Movimiento vinculado a categoría no autorizada')
            g.add((sujeto, FIN.perteneceACategoria, _recurso(
                id_usuario, 'categoria', movimiento.id_categoria
            )))
        if movimiento.id_obligacion is not None:
            if movimiento.id_obligacion not in ids_obligaciones:
                raise ErrorNegocio(CodigoError.CONFLICTO, 'Movimiento vinculado a obligación ajena')
            g.add((sujeto, FIN.relacionadoConObligacion, _recurso(
                id_usuario, 'obligacion', movimiento.id_obligacion
            )))
        g.add((sujeto, FIN.tieneMonto, _dinero(movimiento.monto)))
        g.add((sujeto, FIN.tieneFecha, _fecha(movimiento.fecha_movimiento)))
        g.add((sujeto, OP.estado, _texto(movimiento.estado)))
        g.add((sujeto, OP.origen, _texto(movimiento.origen)))
        g.add((sujeto, OP.tipoMovimiento, _texto(movimiento.tipo)))
        g.add((sujeto, OP.montoGMF, _dinero(movimiento.monto_gmf)))

    transferencias = exportacion.obtener_transferencias(db, id_usuario)
    for tr in transferencias:
        if tr.id_cuenta_destino not in ids_cuentas:
            raise ErrorNegocio(CodigoError.CONFLICTO, 'Transferencia entre propietarios diferentes')
        sujeto = _recurso(id_usuario, 'transferencia', tr.id_transferencia)
        g.add((sujeto, RDF.type, FIN.Transferencia))
        g.add((sujeto, FIN.tieneCuentaOrigen, _recurso(
            id_usuario, 'cuenta', tr.id_cuenta_origen
        )))
        g.add((sujeto, FIN.tieneCuentaDestino, _recurso(
            id_usuario, 'cuenta', tr.id_cuenta_destino
        )))
        g.add((sujeto, FIN.tieneMonto, _dinero(tr.monto)))
        g.add((sujeto, OP.estado, _texto(tr.estado)))

    for meta in metas:
        ligado = vinculados[meta.id_meta]
        antiguo = Decimal(meta.monto_acumulado) - ligado
        if ligado < 0 or antiguo < 0:
            raise ErrorNegocio(CodigoError.CONFLICTO, 'Acumulado de meta inconsistente')
        sujeto = _recurso(id_usuario, 'meta', meta.id_meta)
        g.add((usuario, FIN.tieneMeta, sujeto))
        g.add((sujeto, RDF.type, FIN.MetaFinanciera))
        g.add((sujeto, FIN.tieneNombreMeta, _texto(meta.nombre_meta)))
        g.add((sujeto, FIN.tieneMontoObjetivo, _dinero(meta.monto_objetivo)))
        g.add((sujeto, FIN.tieneMontoAcumulado, _dinero(meta.monto_acumulado)))
        g.add((sujeto, FIN.tieneMontoVinculado, _dinero(ligado)))
        g.add((sujeto, FIN.tieneMontoSinVincular, _dinero(antiguo)))
        g.add((sujeto, OP.estado, _texto(meta.estado)))

    for aporte in aportes:
        if aporte.tipo not in ('RESERVA', 'LIBERACION'):
            raise ErrorNegocio(CodigoError.CONFLICTO, 'Tipo de aporte inconsistente')
        sujeto = _recurso(id_usuario, 'aporte', aporte.id_aporte)
        clase = FIN.ReservaMeta if aporte.tipo == 'RESERVA' else FIN.LiberacionMeta
        g.add((sujeto, RDF.type, clase))
        g.add((sujeto, FIN.correspondeAMeta, _recurso(
            id_usuario, 'meta', aporte.id_meta
        )))
        g.add((sujeto, FIN.seRealizaDesdeCuenta, _recurso(
            id_usuario, 'cuenta', aporte.id_cuenta
        )))
        g.add((sujeto, FIN.registradoPorUsuario, usuario))
        g.add((sujeto, FIN.tieneIdAporte, Literal(aporte.id_aporte, datatype=XSD.integer)))
        g.add((sujeto, FIN.tieneUUIDOperacion, _texto(aporte.uuid_operacion)))
        g.add((sujeto, FIN.tieneMontoAporte, _dinero(aporte.monto)))
        g.add((sujeto, FIN.tieneFechaOperacion, _fecha(aporte.fecha_operacion)))
        g.add((sujeto, FIN.tieneEstadoAporte, _texto(aporte.estado)))

    for ob in obligaciones:
        sujeto = _recurso(id_usuario, 'obligacion', ob.id_obligacion)
        clase = FIN.ObligacionPorPagar if ob.tipo_obligacion == 'POR_PAGAR' else FIN.ObligacionPorCobrar
        g.add((usuario, FIN.tieneObligacion, sujeto))
        g.add((sujeto, RDF.type, clase))
        g.add((sujeto, FIN.tieneNombreObligacion, _texto(ob.nombre_obligacion)))
        g.add((sujeto, FIN.tieneMontoOriginal, _dinero(ob.monto_original)))
        g.add((sujeto, OP.estado, _texto(ob.estado)))

    presupuestos = exportacion.obtener_presupuestos(db, id_usuario)
    for p in presupuestos:
        if p.id_categoria not in ids_categorias:
            raise ErrorNegocio(CodigoError.CONFLICTO, 'Presupuesto vinculado a categoría no autorizada')
        sujeto = _recurso(id_usuario, 'presupuesto', p.id_presupuesto)
        g.add((usuario, FIN.tienePresupuesto, sujeto))
        g.add((sujeto, RDF.type, FIN.Presupuesto))
        g.add((sujeto, FIN.aplicaACategoria, _recurso(
            id_usuario, 'categoria', p.id_categoria
        )))
        g.add((sujeto, FIN.tieneMontoLimite, _dinero(p.monto_limite)))
        g.add((sujeto, OP.anio, Literal(p.anio, datatype=XSD.integer)))
        g.add((sujeto, OP.mes, Literal(p.mes, datatype=XSD.integer)))

    conteos = {
        'cuentas': len(cuentas),
        'categorias': len(categorias),
        'movimientos': len(movimientos),
        'transferencias': len(transferencias),
        'obligaciones': len(obligaciones),
        'presupuestos': len(presupuestos),
        'metas': len(metas),
        'aportes': len(aportes),
    }
    return g, conteos
