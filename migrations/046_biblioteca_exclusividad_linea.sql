-- 046 — Restaura exclusividad: una línea por biblioteca (un solo caso).
-- Revierte 045 si estaba aplicada.

BEGIN;

DELETE FROM public.biblioteca_caso_linea a
USING public.biblioteca_caso_linea b
WHERE a.id > b.id
  AND a.biblioteca_id = b.biblioteca_id
  AND a.linea_id = b.linea_id;

ALTER TABLE public.biblioteca_caso_linea
    DROP CONSTRAINT IF EXISTS biblioteca_caso_linea_caso_linea_uq;

ALTER TABLE public.biblioteca_caso_linea
    DROP CONSTRAINT IF EXISTS biblioteca_caso_linea_bib_linea_uq;

ALTER TABLE public.biblioteca_caso_linea
    ADD CONSTRAINT biblioteca_caso_linea_bib_linea_uq
    UNIQUE (biblioteca_id, linea_id);

COMMENT ON TABLE public.biblioteca_caso_linea IS
  'Exclusividad: cada linea_id una sola vez por biblioteca (un caso).';

COMMIT;

SELECT '046 aplicada: exclusividad línea por biblioteca' AS estado;
