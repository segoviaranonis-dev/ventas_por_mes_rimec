-- 045 — Una misma línea del pilar puede pertenecer a varios casos en la misma biblioteca.
-- Quita exclusividad global biblioteca_id + linea_id; exclusividad solo por (caso, línea).

BEGIN;

ALTER TABLE public.biblioteca_caso_linea
    DROP CONSTRAINT IF EXISTS biblioteca_caso_linea_bib_linea_uq;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'biblioteca_caso_linea_caso_linea_uq'
    ) THEN
        ALTER TABLE public.biblioteca_caso_linea
            ADD CONSTRAINT biblioteca_caso_linea_caso_linea_uq
            UNIQUE (caso_biblioteca_id, linea_id);
    END IF;
END $$;

COMMENT ON TABLE public.biblioteca_caso_linea IS
  'Contenedor por caso: la misma linea_id puede repetirse en distintos caso_biblioteca_id.';

COMMIT;

SELECT '045 aplicada: línea multi-caso en biblioteca' AS estado;
