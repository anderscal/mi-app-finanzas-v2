
from typing import Annotated
from fastapi import Query

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.persistence.database import get_db

from sqlalchemy import select
from app.models import CuentaFinanciera

from app.business.cuenta_service import consultar_resumen_cuentas

from app.business.movimiento_service import (
    consultar_resumen_mensual,
    consultar_historial_mensual
)

from app.business.planificacion_service import (
    consultar_planificacion
)

from app.schemas.movimiento_schema import (
    MovimientoNormalCrear
)

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas.auth_schema import (
    UsuarioRegistro,
    UsuarioRespuesta,
    TokenRespuesta,
)
from app.services.auth_service import (
    registrar_usuario,
    autenticar_usuario,
    crear_access_token,
    obtener_usuario_actual,
)
from app.business.cuenta_service import (
    consultar_resumen_cuentas
)
from app.models import Usuario

from app.schemas.movimiento_schema import (
    MovimientoNormalCrear,
    RegistroMovimientoRespuesta
)

from app.business.movimiento_escritura_service import (
    registrar_movimiento_normal
)

app = FastAPI(
    title="API Finanzas Personales",
    description="Backend del sistema de gestión financiera personal",
    version="1.0.0"
)

# Dependencia de sesión de PostgreSQL
SesionBD = Annotated[Session, Depends(get_db)]


@app.get("/")
def inicio():
    return {
        "mensaje": "Bienvenido a la API de Finanzas Personales",
        "estado": "funcionando"
    }


@app.get("/salud")
def verificar_salud():
    return {
        "servicio": "FastAPI",
        "estado": "activo"
    }


# Endpoint temporal para probar la base de datos
@app.get("/pruebas/cuentas")
def listar_cuentas_prueba(db: SesionBD):

    consulta = (
        select(CuentaFinanciera)
        .where(CuentaFinanciera.id_usuario == 1)
        .order_by(CuentaFinanciera.id_cuenta)
    )

    cuentas = db.scalars(consulta).all()

    return {
        "total": len(cuentas),
        "cuentas": [
            {
                "id_cuenta": cuenta.id_cuenta,
                "nombre_cuenta": cuenta.nombre_cuenta,
                "tipo_cuenta": cuenta.tipo_cuenta,
                "saldo_inicial": cuenta.saldo_inicial,
                "estado": cuenta.estado
            }
            for cuenta in cuentas
        ]
    }


@app.get("/pruebas/resumen-cuentas")
def obtener_resumen_cuentas_prueba(db: SesionBD):

    resumen = consultar_resumen_cuentas(
        db=db,
        id_usuario=1
    )

    return resumen

@app.get("/pruebas/resumen-mensual")
def resumen_mensual_prueba(
    db: SesionBD,
    anio: int = Query(2026, ge=2000, le=9998),
    mes: int = Query(11, ge=1, le=12)
):
    return consultar_resumen_mensual(
        db=db,
        id_usuario=1,
        anio=anio,
        mes=mes
    )


@app.get("/pruebas/historial-mensual")
def historial_mensual_prueba(
    db: SesionBD,
    anio: int = Query(2026, ge=2000, le=9998),
    mes: int = Query(11, ge=1, le=12)
):
    return consultar_historial_mensual(
        db=db,
        id_usuario=1,
        anio=anio,
        mes=mes
    )


@app.get("/pruebas/planificacion")
def obtener_planificacion_prueba(db: SesionBD):

    return consultar_planificacion(
        db=db,
        id_usuario=1
    )


@app.post("/pruebas/validar-movimiento")
def validar_movimiento_prueba(
    datos: MovimientoNormalCrear
):
    return {
        "valido": True,
        "mensaje": "Datos estructuralmente válidos",
        "movimiento": datos.model_dump(
            mode="json"
        )
    }


@app.post(
    "/auth/registro",
    response_model=UsuarioRespuesta,
    status_code=status.HTTP_201_CREATED
)
def registro(
    datos: UsuarioRegistro,
    db: SesionBD
):
    return registrar_usuario(db, datos)


@app.post(
    "/auth/login",
    response_model=TokenRespuesta
)
def login(
    db: SesionBD,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    usuario = autenticar_usuario(
        db,
        form_data.username,
        form_data.password
    )

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = crear_access_token(
        usuario.id_usuario
    )

    return TokenRespuesta(
        access_token=token,
        token_type="bearer"
    )


@app.get(
    "/auth/me",
    response_model=UsuarioRespuesta
)
def mi_perfil(
    usuario: Usuario = Depends(obtener_usuario_actual)
):
    return usuario


@app.get("/auth/mis-cuentas")
def mis_cuentas(
    db: SesionBD,
    usuario: Usuario = Depends(obtener_usuario_actual)
):
    return consultar_resumen_cuentas(
        db=db,
        id_usuario=usuario.id_usuario
    )


@app.post("/movimientos/normales",
    response_model=RegistroMovimientoRespuesta
)
def crear_movimiento_normal(
    datos: MovimientoNormalCrear,
    db: SesionBD,
    usuario: Usuario = Depends(obtener_usuario_actual)
):
    return registrar_movimiento_normal(
        db=db,
        id_usuario=usuario.id_usuario,
        datos=datos
    )
