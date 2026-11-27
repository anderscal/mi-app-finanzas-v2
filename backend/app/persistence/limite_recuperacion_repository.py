from datetime import timedelta

from sqlalchemy import text


# Espacio de bloqueo independiente del utilizado
# para la sincronizacion semantica.

ESPACIO_BLOQUEO = 2845
CLAVE_BLOQUEO = 1


def reservar_cupo(
    db,
    maximo_15_minutos,
    maximo_24_horas,
):

    # Serializar las solicitudes entre procesos.
    # El bloqueo se libera al finalizar la transaccion.

    db.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            ":espacio, :clave)"
        ),
        {
            "espacio": ESPACIO_BLOQUEO,
            "clave": CLAVE_BLOQUEO,
        },
    )

    # Obtener la hora del servidor despues
    # de adquirir el bloqueo.

    ahora = db.scalar(
        text("SELECT clock_timestamp()")
    )

    desde_dia = ahora - timedelta(hours=24)

    desde_ventana = ahora - timedelta(minutes=15)

    # Retirar registros fuera de la ventana diaria.

    db.execute(
        text("""
            DELETE FROM public.limite_recuperacion
            WHERE fecha <= :desde_dia
        """),
        {
            "desde_dia": desde_dia,
        },
    )

    recientes, total = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE fecha > :desde_ventana
                ),

                COUNT(*)

            FROM public.limite_recuperacion
        """),
        {
            "desde_ventana": desde_ventana,
        },
    ).one()

    if (
        recientes >= maximo_15_minutos

        or total >= maximo_24_horas
    ):

        return False

    db.execute(
        text("""
            INSERT INTO public.limite_recuperacion
                (fecha)
            VALUES (:ahora)
        """),
        {
            "ahora": ahora,
        },
    )

    return True