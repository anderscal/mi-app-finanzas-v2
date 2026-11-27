from datetime import timedelta

from sqlalchemy import text


BLOQUEOS = {
    "login": 1,
    "registro": 2,
    "rag": 3,
}


def reservar(db, operacion, sujeto, limites):

    global15, global24, sujeto15, sujeto24 = limites

    db.execute(
        text(
            "SELECT pg_advisory_xact_lock(2853, :clave)"
        ),
        {
            "clave": BLOQUEOS[operacion],
        },
    )

    ahora = db.scalar(
        text("SELECT clock_timestamp()")
    )

    parametros = {
        "op": operacion,
        "sujeto": sujeto,
        "desde15": ahora - timedelta(minutes=15),
        "desde24": ahora - timedelta(hours=24),
        "ahora": ahora,
    }

    db.execute(
        text("""
            DELETE FROM public.limite_operacion
            WHERE operacion = :op
              AND fecha <= :desde24
        """),
        parametros,
    )

    g15, g24, s15, s24 = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE fecha > :desde15
                ),

                COUNT(*),

                COUNT(*) FILTER (
                    WHERE sujeto = :sujeto
                      AND fecha > :desde15
                ),

                COUNT(*) FILTER (
                    WHERE sujeto = :sujeto
                )

            FROM public.limite_operacion
            WHERE operacion = :op
        """),
        parametros,
    ).one()

    if (
        g15 >= global15
        or g24 >= global24
        or s15 >= sujeto15
        or s24 >= sujeto24
    ):

        return False

    db.execute(
        text("""
            INSERT INTO public.limite_operacion
                (operacion, sujeto, fecha)

            VALUES
                (:op, :sujeto, :ahora)
        """),
        parametros,
    )

    return True