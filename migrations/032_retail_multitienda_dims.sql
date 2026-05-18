-- =============================================================================
-- 032 · Dimensiones opcionales (marca, género, estilo, tipo_1) en staging — texto
-- Ejecutar después de 030 si aún no migraste a 033.
-- Si corrés **033**, esa migración elimina estas columnas y reemplaza por FK *_id.
-- =============================================================================

ALTER TABLE public.retail_multitienda_staging
    ADD COLUMN IF NOT EXISTS marca     text NULL,
    ADD COLUMN IF NOT EXISTS genero    text NULL,
    ADD COLUMN IF NOT EXISTS estilo    text NULL,
    ADD COLUMN IF NOT EXISTS tipo_1    text NULL;

COMMENT ON COLUMN public.retail_multitienda_staging.marca IS
  'Marca comercial (Excel opcional).';
COMMENT ON COLUMN public.retail_multitienda_staging.genero IS
  'Género de producto (Excel opcional).';
COMMENT ON COLUMN public.retail_multitienda_staging.estilo IS
  'Estilo (Excel opcional).';
COMMENT ON COLUMN public.retail_multitienda_staging.tipo_1 IS
  'Tipo_1 p. ej. Abierto / Cerrado (Excel opcional).';
