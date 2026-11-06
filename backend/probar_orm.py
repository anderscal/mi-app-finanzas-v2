
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.database import engine
from app.models import Usuario, CuentaFinanciera


with Session(engine) as session:

    print("=== USUARIOS ===")

    consulta_usuarios = select(Usuario)
    usuarios = session.scalars(consulta_usuarios).all()

    for usuario in usuarios:
        print(
            usuario.id_usuario,
            usuario.nombre_1,
            usuario.apellido_1,
            usuario.email
        )

    print("\n=== CUENTAS ===")

    consulta_cuentas = select(CuentaFinanciera)
    cuentas = session.scalars(consulta_cuentas).all()

    for cuenta in cuentas:
        print(
            cuenta.id_cuenta,
            cuenta.nombre_cuenta,
            cuenta.saldo_inicial,
            cuenta.estado
        )

    print("\n=== RELACION USUARIO - CUENTAS ===")

    usuario = session.get(Usuario, 1)

    if usuario is not None:
        print("Usuario:", usuario.nombre_1)

        for cuenta in usuario.cuentas:
            print("Cuenta:", cuenta.nombre_cuenta)
    else:
        print("No existe el usuario 1")
    