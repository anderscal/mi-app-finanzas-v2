BEGIN;

ALTER TABLE public.usuario
ADD COLUMN IF NOT EXISTS version_sesion INTEGER
NOT NULL DEFAULT 0 CHECK (version_sesion >= 0);

CREATE INDEX IF NOT EXISTS idx_token_recuperacion_usuario_expiracion
ON public.token_recuperacion (
    id_usuario,
    fecha_expiracion
);

COMMIT;

SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'usuario'
  AND column_name = 'version_sesion';