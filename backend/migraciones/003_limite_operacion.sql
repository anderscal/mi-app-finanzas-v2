BEGIN;

CREATE TABLE IF NOT EXISTS public.limite_operacion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    operacion VARCHAR(20) NOT NULL
        CHECK (
            operacion IN ('login', 'registro', 'rag')
        ),

    sujeto VARCHAR(64) NOT NULL
        CHECK (
            sujeto ~ '^[0-9a-f]{64}$'
        ),

    fecha TIMESTAMPTZ NOT NULL
        DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_limite_operacion_fecha
ON public.limite_operacion (
    operacion,
    fecha
);

CREATE INDEX IF NOT EXISTS idx_limite_operacion_sujeto
ON public.limite_operacion (
    operacion,
    sujeto,
    fecha
);

COMMIT;