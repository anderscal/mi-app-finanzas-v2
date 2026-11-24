
-- Paso 27.4: seguimiento transaccional de publicaciones RDF.
-- Ejecutar UNA vez sobre la MISMA base PostgreSQL
-- que utiliza FastAPI.
--
-- No modifica movimientos, cuentas ni saldos financieros.

BEGIN;

CREATE TABLE IF NOT EXISTS estado_rdf_usuario (
    id_usuario INTEGER PRIMARY KEY
        REFERENCES usuario(id_usuario) ON DELETE CASCADE,

    revision BIGINT NOT NULL DEFAULT 0
        CHECK (revision >= 0),

    revision_publicada BIGINT NOT NULL DEFAULT 0
        CHECK (
            revision_publicada >= 0
            AND revision_publicada <= revision
        ),

    actualizacion_en TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    publicacion_en TIMESTAMPTZ
);

-- Los usuarios existentes requieren una publicación
-- inicial de reconciliación.
INSERT INTO estado_rdf_usuario (
    id_usuario,
    revision,
    revision_publicada
)
SELECT id_usuario, 1, 0
FROM usuario
ON CONFLICT (id_usuario) DO NOTHING;

COMMIT;

-- Consulta de comprobación.
SELECT COUNT(*) AS usuarios_pendientes
FROM estado_rdf_usuario
WHERE revision > revision_publicada;
