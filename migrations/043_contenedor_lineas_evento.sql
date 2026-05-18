-- ═══════════════════════════════════════════════════════════════════════════
-- 043 — Contenedor de líneas por listado (precio_evento)
--
-- Una línea solo puede pertenecer a un caso dentro del mismo evento.
-- evento_id en precio_evento_linea_excepcion acelera barrera y UNIQUE.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE public.precio_evento_linea_excepcion
    ADD COLUMN IF NOT EXISTS evento_id bigint NULL
        REFERENCES public.precio_evento(id) ON DELETE CASCADE;

UPDATE public.precio_evento_linea_excepcion pele
SET evento_id = pec.evento_id
FROM public.precio_evento_caso pec
WHERE pec.id = pele.caso_id
  AND pele.evento_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_pele_evento_id
    ON public.precio_evento_linea_excepcion (evento_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pele_evento_linea_unica
    ON public.precio_evento_linea_excepcion (evento_id, linea_id)
    WHERE evento_id IS NOT NULL;

COMMENT ON TABLE public.precio_evento_linea_excepcion IS
  'Contenedor FK línea→caso por listado. Barrera 1: Excel solo cruza líneas definidas aquí.';

COMMIT;

SELECT '043 aplicada: contenedor líneas por evento' AS estado;
