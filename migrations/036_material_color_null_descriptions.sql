-- =============================================================================
-- 036 · material / color: permitir descripcion y nombre NULL (Regla 2.1 retail)
-- Alta automática desde Excel retail sin frenar importación; saneamiento luego
-- vía proformas (pedido_proveedor) u operadores.
-- Idempotente: DROP NOT NULL no falla si la columna ya admite NULL.
-- =============================================================================

ALTER TABLE public.material ALTER COLUMN descripcion DROP NOT NULL;
ALTER TABLE public.color ALTER COLUMN nombre DROP NOT NULL;

COMMENT ON COLUMN public.material.descripcion IS
  'Puede ser NULL en altas automáticas desde retail hasta saneamiento (proforma u operador).';
COMMENT ON COLUMN public.color.nombre IS
  'Puede ser NULL en altas automáticas; proforma con descripción cura el pilar (Regla 2.2).';
