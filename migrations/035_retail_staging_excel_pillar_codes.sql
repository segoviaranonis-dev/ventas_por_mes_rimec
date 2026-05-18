-- =============================================================================
-- 035 · retail_multitienda_staging: códigos material/color tal como vienen del Excel
-- Propósito: las FK material_id/color_id pueden apuntar al sentinela RETAIL_OTROS
--            (codigo_proveedor = -999001 en maestro), lo que rompía nombres de foto
--            (doble guion 5881--999001) y perdía el código real de la celda Excel.
--            La app de carga rellena excel_* antes de resolver FKs; el report prioriza
--            esos valores para Storage (misma convención RIMEC/Bazzar).
-- =============================================================================

ALTER TABLE public.retail_multitienda_staging
    ADD COLUMN IF NOT EXISTS excel_material_code text NULL,
    ADD COLUMN IF NOT EXISTS excel_color_code text NULL;

COMMENT ON COLUMN public.retail_multitienda_staging.excel_material_code IS
  'Código material de la celda Excel (antes de resolver a material.id); fotos y trazabilidad.';
COMMENT ON COLUMN public.retail_multitienda_staging.excel_color_code IS
  'Código color de la celda Excel (antes de resolver a color.id); evita usar -999001 del sentinela.';
