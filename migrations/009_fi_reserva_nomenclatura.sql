-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 009: Reestructuración Facturas Internas (FI)
-- ORDEN_TRABAJO_INMEDIATA — 05/05/2026
--
-- Cambios:
--   1. Reset de contadores y limpieza (TRUNCATE factura_interna CASCADE)
--   2. Nuevo paradigma: FI nace con estado 'RESERVADA' (soft-discount)
--   3. Nomenclatura compuesta: [PP_ID]-PV[Correlativo] (ej: 15-PV001)
--   4. Función revertir_stock_fi() mejorada para ANULAR facturas
--   5. Columna nro_factura renombrada desde 'nro' (si existe como 'nro')
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
-- 1. RESET: Limpiar pruebas viejas
-- ───────────────────────────────────────────────────────────────────────────
TRUNCATE TABLE factura_interna CASCADE;

-- Resetear secuencia si existe
ALTER TABLE factura_interna ALTER COLUMN id RESTART WITH 1;

-- ───────────────────────────────────────────────────────────────────────────
-- 2. Renombrar columna 'nro' a 'nro_factura' si aún no existe
-- ───────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
  -- Si existe 'nro' pero no 'nro_factura', renombrar
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'factura_interna' AND column_name = 'nro'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'factura_interna' AND column_name = 'nro_factura'
  ) THEN
    ALTER TABLE factura_interna RENAME COLUMN nro TO nro_factura;
  END IF;
  
  -- Si no existe ninguna, crear nro_factura
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'factura_interna' AND column_name = 'nro_factura'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'factura_interna' AND column_name = 'nro'
  ) THEN
    ALTER TABLE factura_interna ADD COLUMN nro_factura TEXT NOT NULL DEFAULT '';
  END IF;
END $$;

-- ───────────────────────────────────────────────────────────────────────────
-- 3. Asegurar constraint de estado incluye RESERVADA
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE factura_interna
  DROP CONSTRAINT IF EXISTS factura_interna_estado_check;

ALTER TABLE factura_interna
  ADD CONSTRAINT factura_interna_estado_check
  CHECK (estado IN ('RESERVADA', 'CONFIRMADA', 'ANULADA'));

-- Default a RESERVADA (soft-discount al nacer)
ALTER TABLE factura_interna
  ALTER COLUMN estado SET DEFAULT 'RESERVADA';

-- ───────────────────────────────────────────────────────────────────────────
-- 4. Función: Generar número de FI con nomenclatura [PP_ID]-PV[NNN]
--    El correlativo se resetea por cada Pedido Proveedor
-- ───────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION generar_nro_factura_interna(p_pp_id BIGINT)
RETURNS TEXT AS $$
DECLARE
  v_correlativo INTEGER;
  v_nro TEXT;
BEGIN
  -- Obtener el máximo correlativo para este PP
  SELECT COALESCE(
    MAX(
      CAST(
        REGEXP_REPLACE(nro_factura, '^[0-9]+-PV', '')
        AS INTEGER
      )
    ),
    0
  ) + 1
  INTO v_correlativo
  FROM factura_interna
  WHERE pp_id = p_pp_id
    AND nro_factura ~ '^[0-9]+-PV[0-9]+$';

  -- Formato: [PP_ID]-PV[NNN] (ej: 15-PV001)
  v_nro := p_pp_id::TEXT || '-PV' || LPAD(v_correlativo::TEXT, 3, '0');
  
  RETURN v_nro;
END;
$$ LANGUAGE plpgsql;

-- ───────────────────────────────────────────────────────────────────────────
-- 5. Función: Revertir stock cuando FI es ANULADA
--    Devuelve mercadería al tránsito (decrementa pares_vendidos en PPD)
-- ───────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION revertir_stock_fi(p_fi_id BIGINT)
RETURNS void AS $$
DECLARE
  v_fi_estado TEXT;
BEGIN
  -- Verificar que la FI existe y obtener estado actual
  SELECT estado INTO v_fi_estado
  FROM factura_interna
  WHERE id = p_fi_id;
  
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Factura Interna % no encontrada', p_fi_id;
  END IF;
  
  -- Solo revertir si está siendo ANULADA (no si ya estaba anulada)
  -- La reversión se ejecuta ANTES de cambiar el estado a ANULADA
  
  -- Reversión por ppd_id directo (facturas creadas desde PP con det_id)
  UPDATE pedido_proveedor_detalle ppd
  SET pares_vendidos = GREATEST(0, COALESCE(pares_vendidos, 0) - fid.pares)
  FROM factura_interna_detalle fid
  WHERE fid.factura_id = p_fi_id
    AND fid.ppd_id IS NOT NULL
    AND ppd.id = fid.ppd_id;

  -- Reversión por snapshot (facturas sin ppd_id directo)
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
    
  -- Marcar como ANULADA
  UPDATE factura_interna
  SET estado = 'ANULADA'
  WHERE id = p_fi_id;
END;
$$ LANGUAGE plpgsql;

-- ───────────────────────────────────────────────────────────────────────────
-- 6. Función: Crear FI con estado RESERVADA y nomenclatura automática
--    Esta función encapsula la lógica de creación para garantizar consistencia
-- ───────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION crear_factura_interna_reservada(
  p_pp_id           BIGINT,
  p_cliente_id      BIGINT,
  p_vendedor_id     BIGINT DEFAULT NULL,
  p_categoria_id    INTEGER DEFAULT NULL,
  p_total_pares     INTEGER DEFAULT 0,
  p_total_monto     NUMERIC DEFAULT 0
)
RETURNS BIGINT AS $$
DECLARE
  v_nro_factura TEXT;
  v_fi_id BIGINT;
BEGIN
  -- Generar número con nomenclatura [PP_ID]-PV[NNN]
  v_nro_factura := generar_nro_factura_interna(p_pp_id);
  
  -- Insertar con estado RESERVADA (soft-discount)
  INSERT INTO factura_interna (
    pp_id, nro_factura, cliente_id, vendedor_id,
    categoria_id, total_pares, total_monto, estado
  ) VALUES (
    p_pp_id, v_nro_factura, p_cliente_id, p_vendedor_id,
    p_categoria_id, p_total_pares, p_total_monto, 'RESERVADA'
  )
  RETURNING id INTO v_fi_id;
  
  RETURN v_fi_id;
END;
$$ LANGUAGE plpgsql;

-- ───────────────────────────────────────────────────────────────────────────
-- 7. Agregar columna categoria_id si no existe (trazabilidad)
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE factura_interna
  ADD COLUMN IF NOT EXISTS categoria_id INTEGER;

-- ───────────────────────────────────────────────────────────────────────────
-- 8. Índice único para evitar duplicados de nomenclatura
-- ───────────────────────────────────────────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS idx_fi_nro_factura_unique
  ON factura_interna (nro_factura);

COMMIT;
