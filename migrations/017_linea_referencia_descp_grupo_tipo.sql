-- 017 — linea_referencia: unificar nombres con maestras (descp_grupo_estilo, descp_tipo_1)
-- Ejecutar en Supabase tras backup.
--
-- Renombra columnas legacy si existían; si no, crea las columnas de denormalización TEXT.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'linea_referencia'
          AND column_name = 'estilo'
    ) THEN
        ALTER TABLE linea_referencia RENAME COLUMN estilo TO descp_grupo_estilo;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'linea_referencia'
          AND column_name = 'tipo_1'
    ) THEN
        ALTER TABLE linea_referencia RENAME COLUMN tipo_1 TO descp_tipo_1;
    END IF;
END $$;

ALTER TABLE linea_referencia ADD COLUMN IF NOT EXISTS descp_grupo_estilo TEXT;
ALTER TABLE linea_referencia ADD COLUMN IF NOT EXISTS descp_tipo_1 TEXT;

COMMIT;
