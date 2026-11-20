
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from app.tests.helpers import (
    crear_usuario_autenticado,
    crear_cuenta,
    obtener_categoria_sistema,
)


def monto(valor):
    return Decimal(str(valor))


def crear_meta_qa(
    client,
    headers,
    nombre,
    objetivo="10000.00"
):
    respuesta = client.post(
        "/metas/",
        headers=headers,
        json={
            "nombre_meta": nombre,
            "monto_objetivo": objetivo,
            "fecha_objetivo": (
                date.today() + timedelta(days=60)
            ).isoformat(),
            "descripcion": "Prueba de saldo libre",
        }
    )

    assert respuesta.status_code == 201

    return respuesta.json()["id_meta"]


def operar_reserva(
    client,
    headers,
    id_meta,
    id_cuenta,
    cantidad,
    liberar=False
):
    ruta = (
        f"/metas/{id_meta}/liberaciones"
        if liberar
        else f"/metas/{id_meta}/reservas"
    )

    return client.post(
        ruta,
        headers=headers,
        json={
            "uuid_operacion": str(uuid4()),
            "id_cuenta": id_cuenta,
            "monto": cantidad,
            "fecha_operacion": date.today().isoformat(),
        }
    )


def preparar_reserva(
    client,
    headers,
    id_cuenta,
    cantidad,
    nombre
):
    id_meta = crear_meta_qa(
        client,
        headers,
        nombre
    )

    respuesta = operar_reserva(
        client,
        headers,
        id_meta,
        id_cuenta,
        cantidad
    )

    assert respuesta.status_code == 201

    return id_meta


def consultar_saldo(
    client,
    headers,
    id_cuenta
):
    respuesta = client.get(
        "/metas/reservas/cuentas",
        headers=headers
    )

    assert respuesta.status_code == 200

    return next(
        cuenta
        for cuenta in respuesta.json()
        if cuenta["id_cuenta"] == id_cuenta
    )


def registrar_normal(
    client,
    headers,
    id_cuenta,
    id_categoria,
    tipo,
    cantidad,
    uuid=None
):
    return client.post(
        "/movimientos/normales",
        headers=headers,
        json={
            "uuid_local": uuid or str(uuid4()),
            "id_cuenta": id_cuenta,
            "id_categoria": id_categoria,
            "tipo": tipo,
            "monto": cantidad,
            "fecha_movimiento": date.today().isoformat(),
            "descripcion": "QA protección de ahorro",
        }
    )


def transferir(
    client,
    headers,
    origen,
    destino,
    cantidad,
    gmf=False,
    uuid=None
):
    return client.post(
        "/transferencias/",
        headers=headers,
        json={
            "uuid_operacion": uuid or str(uuid4()),
            "id_cuenta_origen": origen,
            "id_cuenta_destino": destino,
            "monto": cantidad,
            "fecha_transferencia": date.today().isoformat(),
            "motivo": "Transferencia QA reservas",
            "aplica_gmf": gmf,
        }
    )


def crear_obligacion(
    client,
    headers,
    nombre,
    tipo,
    cantidad,
    id_cuenta=None,
    uuid=None
):
    inicial = id_cuenta is not None

    return client.post(
        "/obligaciones/",
        headers=headers,
        json={
            "nombre_obligacion": nombre,
            "tipo_obligacion": tipo,
            "monto_original": cantidad,
            "fecha_inicio": date.today().isoformat(),
            "fecha_vencimiento": None,
            "descripcion": "QA reservas",
            "registrar_movimiento_inicial": inicial,
            "id_cuenta_inicial": id_cuenta,
            "uuid_local_inicial": (
                uuid or str(uuid4())
                if inicial
                else None
            ),
            "aplica_gmf_inicial": False,
        }
    )


def registrar_abono(
    client,
    headers,
    id_obligacion,
    id_cuenta,
    cantidad,
    uuid=None
):
    return client.post(
        "/obligaciones/abonos",
        headers=headers,
        json={
            "uuid_local": uuid or str(uuid4()),
            "id_cuenta": id_cuenta,
            "id_obligacion": id_obligacion,
            "monto": cantidad,
            "fecha_movimiento": date.today().isoformat(),
            "descripcion": "Abono QA reservas",
        }
    )


def test_gasto_respeta_saldo_reservado(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.251c.gasto@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta gastos protegidos",
        "1000.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    preparar_reserva(
        client,
        headers,
        cuenta.id_cuenta,
        "700.00",
        "Meta proteger gastos"
    )

    rechazada = registrar_normal(
        client,
        headers,
        cuenta.id_cuenta,
        categoria.id_categoria,
        "GASTO",
        "400.00"
    )

    assert rechazada.status_code == 409
    assert "Saldo libre" in rechazada.json()["detail"]

    uuid = str(uuid4())

    aceptada = registrar_normal(
        client,
        headers,
        cuenta.id_cuenta,
        categoria.id_categoria,
        "GASTO",
        "300.00",
        uuid
    )

    assert aceptada.status_code == 200
    assert aceptada.json()["creado"] is True

    repetida = registrar_normal(
        client,
        headers,
        cuenta.id_cuenta,
        categoria.id_categoria,
        "GASTO",
        "300.00",
        uuid
    )

    assert repetida.status_code == 200
    assert repetida.json()["creado"] is False

    saldo = consultar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert monto(saldo["saldo_real"]) == Decimal("700.00")
    assert monto(saldo["monto_reservado"]) == Decimal("700.00")
    assert monto(saldo["saldo_libre"]) == Decimal("0.00")


def test_transferencia_valida_gmf_y_reservas(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.251c.transferir@example.com"
    )

    origen = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Origen GMF y reservas",
        "1000.00"
    )

    destino = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Destino GMF y reservas",
        "100.00"
    )

    preparar_reserva(
        client,
        headers,
        origen.id_cuenta,
        "600.00",
        "Meta proteger transferencias"
    )

    # Solo hay 400 libres.
    # Transferir 400 con GMF exige 401.60.
    rechazada = transferir(
        client,
        headers,
        origen.id_cuenta,
        destino.id_cuenta,
        "400.00",
        gmf=True
    )

    assert rechazada.status_code == 409

    uuid = str(uuid4())

    aceptada = transferir(
        client,
        headers,
        origen.id_cuenta,
        destino.id_cuenta,
        "398.00",
        gmf=True,
        uuid=uuid
    )

    assert aceptada.status_code == 200
    assert aceptada.json()["creado"] is True

    assert monto(
        aceptada.json()["monto_gmf"]
    ) == Decimal("1.59")

    repetida = transferir(
        client,
        headers,
        origen.id_cuenta,
        destino.id_cuenta,
        "398.00",
        gmf=True,
        uuid=uuid
    )

    assert repetida.status_code == 200
    assert repetida.json()["creado"] is False

    saldo_origen = consultar_saldo(
        client,
        headers,
        origen.id_cuenta
    )

    saldo_destino = consultar_saldo(
        client,
        headers,
        destino.id_cuenta
    )

    assert monto(
        saldo_origen["saldo_real"]
    ) == Decimal("600.41")

    assert monto(
        saldo_origen["saldo_libre"]
    ) == Decimal("0.41")

    assert monto(
        saldo_destino["saldo_real"]
    ) == Decimal("498.00")


def test_pago_deuda_respetando_reservas_e_idempotencia(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.251c.pagar@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta pagar deuda",
        "1000.00"
    )

    id_meta = preparar_reserva(
        client,
        headers,
        cuenta.id_cuenta,
        "800.00",
        "Meta proteger pagos"
    )

    creada = crear_obligacion(
        client,
        headers,
        "Deuda QA protegida",
        "POR_PAGAR",
        "250.00"
    )

    assert creada.status_code == 201

    id_obligacion = creada.json()["id_obligacion"]

    rechazada = registrar_abono(
        client,
        headers,
        id_obligacion,
        cuenta.id_cuenta,
        "250.00"
    )

    assert rechazada.status_code == 409

    primer_pago = registrar_abono(
        client,
        headers,
        id_obligacion,
        cuenta.id_cuenta,
        "200.00"
    )

    assert primer_pago.status_code == 200

    liberar = operar_reserva(
        client,
        headers,
        id_meta,
        cuenta.id_cuenta,
        "100.00",
        liberar=True
    )

    assert liberar.status_code == 201

    uuid_final = str(uuid4())

    pago_final = registrar_abono(
        client,
        headers,
        id_obligacion,
        cuenta.id_cuenta,
        "50.00",
        uuid_final
    )

    assert pago_final.status_code == 200

    assert monto(
        pago_final.json()["monto_pendiente"]
    ) == Decimal("0.00")

    # El UUID sigue funcionando aunque
    # la obligación ya esté SALDADA.
    repetida = registrar_abono(
        client,
        headers,
        id_obligacion,
        cuenta.id_cuenta,
        "50.00",
        uuid_final
    )

    assert repetida.status_code == 200
    assert repetida.json()["creado"] is False

    saldo = consultar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert monto(saldo["saldo_real"]) == Decimal("750.00")
    assert monto(saldo["monto_reservado"]) == Decimal("700.00")
    assert monto(saldo["saldo_libre"]) == Decimal("50.00")


def test_prestamo_entregado_no_utiliza_reservas(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.251c.prestamo@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta capital prestado",
        "1000.00"
    )

    preparar_reserva(
        client,
        headers,
        cuenta.id_cuenta,
        "800.00",
        "Meta proteger préstamo"
    )

    rechazada = crear_obligacion(
        client,
        headers,
        "Préstamo mayor que libre",
        "POR_COBRAR",
        "250.00",
        cuenta.id_cuenta
    )

    assert rechazada.status_code == 409

    uuid = str(uuid4())

    aceptada = crear_obligacion(
        client,
        headers,
        "Préstamo permitido",
        "POR_COBRAR",
        "200.00",
        cuenta.id_cuenta,
        uuid
    )

    assert aceptada.status_code == 201

    repetida = crear_obligacion(
        client,
        headers,
        "Préstamo permitido",
        "POR_COBRAR",
        "200.00",
        cuenta.id_cuenta,
        uuid
    )

    assert repetida.status_code == 201

    assert (
        repetida.json()["id_obligacion"]
        == aceptada.json()["id_obligacion"]
    )

    saldo = consultar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert monto(saldo["saldo_real"]) == Decimal("800.00")
    assert monto(saldo["monto_reservado"]) == Decimal("800.00")
    assert monto(saldo["saldo_libre"]) == Decimal("0.00")

    plan = client.get(
        "/consultas/planificacion",
        headers=headers
    )

    pendiente = next(
        o["monto_pendiente"]
        for o in plan.json()["obligaciones"]
        if (
            o["id_obligacion"]
            == aceptada.json()["id_obligacion"]
        )
    )

    assert monto(pendiente) == Decimal("200.00")


def test_no_anular_ingreso_que_respalda_reserva(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.251c.anular.ingreso@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta ingreso protegido",
        "0.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "INGRESO"
    )

    ingreso = registrar_normal(
        client,
        headers,
        cuenta.id_cuenta,
        categoria.id_categoria,
        "INGRESO",
        "1000.00"
    )

    assert ingreso.status_code == 200

    id_meta = preparar_reserva(
        client,
        headers,
        cuenta.id_cuenta,
        "800.00",
        "Meta ingreso protegido"
    )

    ruta = (
        f"/movimientos/"
        f"{ingreso.json()['id_movimiento']}/anular"
    )

    rechazada = client.post(
        ruta,
        headers=headers
    )

    assert rechazada.status_code == 409

    saldo = consultar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert monto(saldo["saldo_real"]) == Decimal("1000.00")

    liberar = operar_reserva(
        client,
        headers,
        id_meta,
        cuenta.id_cuenta,
        "800.00",
        liberar=True
    )

    assert liberar.status_code == 201

    anulada = client.post(
        ruta,
        headers=headers
    )

    assert anulada.status_code == 200

    saldo_final = consultar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert monto(
        saldo_final["saldo_real"]
    ) == Decimal("0.00")


def test_anular_transferencia_con_destino_reservado(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.251c.anular.transferencia@example.com"
    )

    origen = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Origen anular transferencia",
        "1000.00"
    )

    destino = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Destino anular transferencia",
        "0.00"
    )

    transferencia = transferir(
        client,
        headers,
        origen.id_cuenta,
        destino.id_cuenta,
        "500.00"
    )

    assert transferencia.status_code == 200

    id_meta = preparar_reserva(
        client,
        headers,
        destino.id_cuenta,
        "300.00",
        "Meta transferencias recibidas"
    )

    ruta = (
        "/movimientos/"
        f"{transferencia.json()['id_movimiento_entrada']}"
        "/anular"
    )

    rechazada = client.post(
        ruta,
        headers=headers
    )

    assert rechazada.status_code == 409

    liberar = operar_reserva(
        client,
        headers,
        id_meta,
        destino.id_cuenta,
        "300.00",
        liberar=True
    )

    assert liberar.status_code == 201

    anulada = client.post(
        ruta,
        headers=headers
    )

    assert anulada.status_code == 200

    saldo_origen = consultar_saldo(
        client,
        headers,
        origen.id_cuenta
    )

    saldo_destino = consultar_saldo(
        client,
        headers,
        destino.id_cuenta
    )

    assert monto(
        saldo_origen["saldo_real"]
    ) == Decimal("1000.00")

    assert monto(
        saldo_destino["saldo_real"]
    ) == Decimal("0.00")


def test_no_anular_cobro_que_respalda_reservas(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.251c.anular.cobro@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta cobros protegidos",
        "0.00"
    )

    creada = crear_obligacion(
        client,
        headers,
        "Dinero por cobrar QA",
        "POR_COBRAR",
        "500.00"
    )

    assert creada.status_code == 201

    id_obligacion = creada.json()["id_obligacion"]

    cobro = registrar_abono(
        client,
        headers,
        id_obligacion,
        cuenta.id_cuenta,
        "500.00"
    )

    assert cobro.status_code == 200

    id_meta = preparar_reserva(
        client,
        headers,
        cuenta.id_cuenta,
        "300.00",
        "Meta cobro protegido"
    )

    ruta = (
        "/movimientos/"
        f"{cobro.json()['id_movimiento']}"
        "/anular"
    )

    rechazada = client.post(
        ruta,
        headers=headers
    )

    assert rechazada.status_code == 409

    liberar = operar_reserva(
        client,
        headers,
        id_meta,
        cuenta.id_cuenta,
        "300.00",
        liberar=True
    )

    assert liberar.status_code == 201

    anulada = client.post(
        ruta,
        headers=headers
    )

    assert anulada.status_code == 200

    detalle = client.get(
        f"/obligaciones/{id_obligacion}",
        headers=headers
    )

    assert detalle.status_code == 200
    assert detalle.json()["estado"] == "ACTIVA"


def test_sincronizacion_rechazada_no_duplica(
    client,
    db_session
):
    """
    Simula un gasto que fue guardado offline
    y llega al backend después de una reserva.

    La cola JavaScript se comprueba en la PWA;
    aquí verificamos el contrato HTTP 409
    y la idempotencia de la repetición.
    """
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.251c.sync@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta simulación offline",
        "1000.00"
    )

    categoria = obtener_categoria_sistema(
        db_session,
        "GASTO"
    )

    uuid_guardado = str(uuid4())

    id_meta = preparar_reserva(
        client,
        headers,
        cuenta.id_cuenta,
        "700.00",
        "Meta protegida durante sync"
    )

    primera = registrar_normal(
        client,
        headers,
        cuenta.id_cuenta,
        categoria.id_categoria,
        "GASTO",
        "500.00",
        uuid_guardado
    )

    assert primera.status_code == 409

    saldo = consultar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert monto(saldo["saldo_real"]) == Decimal("1000.00")
    assert monto(saldo["monto_reservado"]) == Decimal("700.00")

    liberar = operar_reserva(
        client,
        headers,
        id_meta,
        cuenta.id_cuenta,
        "300.00",
        liberar=True
    )

    assert liberar.status_code == 201

    # Reintentar el mismo UUID y los mismos datos
    # después de resolver el saldo libre.
    segunda = registrar_normal(
        client,
        headers,
        cuenta.id_cuenta,
        categoria.id_categoria,
        "GASTO",
        "500.00",
        uuid_guardado
    )

    assert segunda.status_code == 200
    assert segunda.json()["creado"] is True

    tercera = registrar_normal(
        client,
        headers,
        cuenta.id_cuenta,
        categoria.id_categoria,
        "GASTO",
        "500.00",
        uuid_guardado
    )

    assert tercera.status_code == 200
    assert tercera.json()["creado"] is False

    saldo_final = consultar_saldo(
        client,
        headers,
        cuenta.id_cuenta
    )

    assert monto(
        saldo_final["saldo_real"]
    ) == Decimal("500.00")

    assert monto(
        saldo_final["monto_reservado"]
    ) == Decimal("400.00")

    assert monto(
        saldo_final["saldo_libre"]
    ) == Decimal("100.00")


def test_no_desactivar_cuenta_con_reservas(
    client,
    db_session
):
    usuario, headers = crear_usuario_autenticado(
        client,
        db_session,
        "qa.251c.cuenta@example.com"
    )

    cuenta = crear_cuenta(
        db_session,
        usuario.id_usuario,
        "Cuenta con ahorro reservado",
        "1000.00"
    )

    preparar_reserva(
        client,
        headers,
        cuenta.id_cuenta,
        "300.00",
        "Meta impedir desactivación"
    )

    respuesta = client.post(
        f"/cuentas/{cuenta.id_cuenta}/desactivar",
        headers=headers
    )

    assert respuesta.status_code == 409

    assert "reservado" in respuesta.json()[
        "detail"
    ].lower()
