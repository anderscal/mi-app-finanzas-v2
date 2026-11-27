BEGIN;

CREATE TABLE IF NOT EXISTS public.limite_recuperacion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    fecha TIMESTAMPTZ NOT NULL
        DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_limite_recuperacion_fecha
ON public.limite_recuperacion (fecha);

COMMIT;