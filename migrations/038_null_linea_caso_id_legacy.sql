-- ═══════════════════════════════════════════════════════════════════════════
-- 038 — Saneamiento linea.caso_id (legacy)
--
-- Ejecutar DESPUÉS de 037. El caso comercial ya no vive en el pilar linea.
-- Idempotente: solo filas con caso_id NOT NULL.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- Preview (no modifica)
-- SELECT COUNT(*) AS filas_con_caso_id FROM public.linea WHERE caso_id IS NOT NULL;

UPDATE public.linea
SET caso_id = NULL
WHERE caso_id IS NOT NULL;

COMMIT;

-- Verificación
SELECT
    COUNT(*) FILTER (WHERE caso_id IS NOT NULL) AS lineas_con_caso_id,
    COUNT(*) AS total_lineas
FROM public.linea;
