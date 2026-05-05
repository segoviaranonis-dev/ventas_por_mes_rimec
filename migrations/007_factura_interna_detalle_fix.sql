-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 007: factura_interna_detalle — columnas faltantes + NOT NULL fix
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ppd_id puede llegar null si el item del payload no tiene det_id
ALTER TABLE factura_interna_detalle
  ALTER COLUMN ppd_id DROP NOT NULL;

-- Columnas que el INSERT necesita pero no existían
ALTER TABLE factura_interna_detalle
  ADD COLUMN IF NOT EXISTS precio_neto    NUMERIC,
  ADD COLUMN IF NOT EXISTS linea_snapshot JSONB;

COMMIT;
