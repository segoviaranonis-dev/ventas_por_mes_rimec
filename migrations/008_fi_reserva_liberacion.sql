-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 008: Flujo Reserva → Liberación de Factura Interna
-- ORDEN_REESTRUCTURACION_FI — Paradigma: BD como único canal
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
-- 1. Expandir estados: agregar RESERVADA al CHECK constraint
--    Estado inicial: RESERVADA (soft-discount, pendiente aprobación)
--    Estado final:   CONFIRMADA (descuento definitivo, aprobada)
--    Estado rechazo: ANULADA (reversión automática de stock)
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE factura_interna
  DROP CONSTRAINT IF EXISTS factura_interna_estado_check;

ALTER TABLE factura_interna
  ADD CONSTRAINT factura_interna_estado_check
  CHECK (estado IN ('RESERVADA', 'CONFIRMADA', 'ANULADA'));

-- ───────────────────────────────────────────────────────────────────────────
-- 2. Columna notas — para motivo de anulación
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE factura_interna
  ADD COLUMN IF NOT EXISTS notas TEXT;

-- ───────────────────────────────────────────────────────────────────────────
-- 3. Función de reversión de stock
--    Restaura pares_vendidos en PPD cuando una FI es anulada
-- ───────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION revertir_stock_fi(p_fi_id BIGINT)
RETURNS void AS $$
BEGIN
  -- Reversión por ppd_id directo (facturas creadas desde PP con det_id)
  UPDATE pedido_proveedor_detalle ppd
  SET pares_vendidos = GREATEST(0, COALESCE(pares_vendidos, 0) - fid.pares)
  FROM factura_interna_detalle fid
  WHERE fid.factura_id = p_fi_id
    AND fid.ppd_id IS NOT NULL
    AND ppd.id = fid.ppd_id;

  -- Reversión por snapshot (facturas creadas desde aprobación PVR sin ppd_id)
  UPDATE pedido_proveedor_detalle ppd
  SET pares_vendidos = GREATEST(0, COALESCE(pares_vendidos, 0) - fid.pares)
  FROM factura_interna_detalle fid
  JOIN factura_interna fi ON fi.id = fid.factura_id
  WHERE fid.factura_id = p_fi_id
    AND fid.ppd_id IS NULL
    AND fid.linea_snapshot IS NOT NULL
    AND ppd.pedido_proveedor_id = fi.pp_id
    AND ppd.linea::text = fid.linea_snapshot::jsonb->>'linea_codigo'
    AND ppd.referencia::text = fid.linea_snapshot::jsonb->>'ref_codigo';
END;
$$ LANGUAGE plpgsql;

-- ───────────────────────────────────────────────────────────────────────────
-- 4. Índice para búsqueda por estado (acelera get_fi_reservadas)
-- ───────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_fi_estado
  ON factura_interna (estado);

COMMIT;
