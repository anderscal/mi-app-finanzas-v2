
"""Acceso semántico autenticado y limitado a consultas predefinidas."""

from decimal import Decimal, InvalidOperation
import os

from fastapi import APIRouter, HTTPException

from app.dependencies import SesionBD, UsuarioActual
from app.business.semantica_service import (
    FIN, OP, construir_grafo_usuario, iri_grafo,
)
from app.services.fuseki_client import (
    FusekiNoDisponible, consultar_select, publicar_grafo,
)

router = APIRouter(prefix='/semantica', tags=['Conocimiento semántico'])


@router.post('/sincronizar')
def sincronizar_semantica(db: SesionBD, usuario: UsuarioActual):
    """Actualiza solo el grafo RDF del usuario autenticado.

    Es una proyección de lectura, no realiza movimientos bancarios.
    """
    if os.getenv("SEMANTICA_EXPORTACION_LOCAL", "0") != "1":
        raise HTTPException(403, "La exportación RDF local no está habilitada")
    grafo, conteos = construir_grafo_usuario(db, usuario.id_usuario)
    try:
        publicar_grafo(grafo, iri_grafo(usuario.id_usuario))
    except FusekiNoDisponible as exc:
        raise HTTPException(503, str(exc)) from exc
    return {
        'resultado': 'sincronizado',
        'id_usuario': usuario.id_usuario,
        'triples': len(grafo),
        'entidades': conteos,
        'nota': 'Instantánea RDF; PostgreSQL es la fuente de verdad',
    }


@router.get('/cuentas')
def consultar_cuentas_semanticas(usuario: UsuarioActual):
    """Consulta SPARQL fija: sin parámetros de grafo ni SPARQL del cliente."""
    grafo = iri_grafo(usuario.id_usuario)
    consulta = f'''
        PREFIX fin: <{FIN}>
        PREFIX op: <{OP}>
        SELECT ?id ?nombre ?real ?reservado ?libre
        WHERE {{
          GRAPH <{grafo}> {{
            ?cuenta a fin:CuentaFinanciera ;
                    op:idCuenta ?id ;
                    fin:tieneNombreCuenta ?nombre ;
                    fin:tieneSaldoReal ?real ;
                    fin:tieneMontoReservado ?reservado ;
                    fin:tieneSaldoLibre ?libre .
          }}
        }} ORDER BY ?id
    '''
    try:
        filas = consultar_select(consulta)
    except FusekiNoDisponible as exc:
        raise HTTPException(503, str(exc)) from exc
    cuentas = []
    for fila in filas:
        try:
            datos = {k: fila[k]['value'] for k in
                     ('id', 'nombre', 'real', 'reservado', 'libre')}
            real = Decimal(datos['real'])
            reservado = Decimal(datos['reservado'])
            libre = Decimal(datos['libre'])
            if real - reservado != libre:
                raise ValueError('Saldo RDF inconsistente')
            cuentas.append({
                'id_cuenta': int(datos['id']),
                'nombre_cuenta': datos['nombre'],
                'saldo_real': str(real),
                'monto_reservado': str(reservado),
                'saldo_libre': str(libre),
            })
        except (KeyError, ValueError, InvalidOperation, TypeError) as exc:
            raise HTTPException(502, 'Respuesta semántica inconsistente') from exc
    return {
        'id_usuario': usuario.id_usuario,
        'fuente': 'Fuseki/TDB2 (última sincronización)',
        'actualizacion_automatica': False,
        'cuentas': cuentas,
    }
