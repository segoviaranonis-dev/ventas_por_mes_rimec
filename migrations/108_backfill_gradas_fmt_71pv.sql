-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 108: Backfill gradas_fmt en 71 PVs existentes
--
-- PROBLEMA:
--   Las 71 PVs (322 items) NO tienen gradas_fmt en linea_snapshot.
--   El PDF muestra "—" en lugar de las tallas compradas.
--
-- SOLUCIÓN:
--   Copiar grades_json desde pedido_proveedor_detalle (stock disponible)
--   y formatearlo como "35:2 · 36:3 · 37:1" en linea_snapshot.gradas_fmt
--
-- CONTEXTO:
--   - Frontend (rimec-web) NO enviaba gradas_fmt al confirmar pedido
--   - Tenemos grades_json en PPD (stock del que se sacó)
--   - Asumimos que las gradas compradas ≈ gradas disponibles en ese momento
--
-- RESULTADO:
--   322 items actualizados con gradas_fmt para PDF auditable
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── Función helper: Formatear grades_json como string ─────────────────────
CREATE OR REPLACE FUNCTION _fmt_grades_json(p_grades_json JSONB)
RETURNS TEXT AS $$
DECLARE
  v_result TEXT := '';
  v_key TEXT;
  v_val TEXT;
  v_sorted JSONB;
BEGIN
  IF p_grades_json IS NULL OR p_grades_json = '{}'::JSONB THEN
    RETURN '';
  END IF;

  -- Ordenar por clave numérica y formatear como "35:2 · 36:3"
  SELECT jsonb_object_agg(
    key::TEXT,
    value
    ORDER BY key::NUMERIC
  )
  INTO v_sorted
  FROM jsonb_each(p_grades_json);

  SELECT string_agg(
    key || ':' || value,
    ' · '
    ORDER BY key::NUMERIC
  )
  INTO v_result
  FROM jsonb_each_text(v_sorted);

  RETURN COALESCE(v_result, '');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ── Backfill: Actualizar linea_snapshot.gradas_fmt desde PPD ──────────────
WITH items_a_actualizar AS (
  SELECT
    fid.id AS fid_id,
    fid.linea_snapshot,
    ppd.grades_json,
    _fmt_grades_json(ppd.grades_json) AS gradas_fmt_nuevo
  FROM factura_interna fi
  JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
  JOIN pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
  WHERE fi.pv_global IS NOT NULL
    AND (
      fid.linea_snapshot->>'gradas_fmt' IS NULL
      OR fid.linea_snapshot->>'gradas_fmt' = ''
    )
)
UPDATE factura_interna_detalle fid
SET linea_snapshot = jsonb_set(
  fid.linea_snapshot,
  '{gradas_fmt}',
  to_jsonb(items.gradas_fmt_nuevo)
)
FROM items_a_actualizar items
WHERE fid.id = items.fid_id;

-- ── Limpieza: Eliminar función helper temporal ─────────────────────────────
DROP FUNCTION IF EXISTS _fmt_grades_json(JSONB);

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN:
-- ═══════════════════════════════════════════════════════════════════════════
-- SELECT
--   COUNT(*) AS total_items,
--   COUNT(*) FILTER (WHERE linea_snapshot->>'gradas_fmt' != '') AS con_gradas,
--   COUNT(*) FILTER (WHERE linea_snapshot->>'gradas_fmt' = '') AS sin_gradas
-- FROM factura_interna fi
-- JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
-- WHERE fi.pv_global IS NOT NULL;
--
-- -- Ver ejemplos:
-- SELECT
--   fi.pv_global,
--   fi.nro_factura,
--   fid.pares,
--   fid.linea_snapshot->>'gradas_fmt' AS gradas_fmt
-- FROM factura_interna fi
-- JOIN factura_interna_detalle fid ON fid.factura_id = fi.id
-- WHERE fi.pv_global IS NOT NULL
-- ORDER BY fi.pv_global DESC
-- LIMIT 10;
-- ═══════════════════════════════════════════════════════════════════════════