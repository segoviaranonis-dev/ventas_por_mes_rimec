-- 047 — v_stock_rimec: JOIN linea_referencia por linea.id + referencia.id (no por códigos casteados)
-- Ejecutar el cuerpo de scripts/fix_v_stock_rimec.py o este archivo en Supabase.

-- La definición canónica está en scripts/fix_v_stock_rimec.py (CREATE OR REPLACE VIEW v_stock_rimec).
-- Cambio clave respecto a versiones anteriores:
--   LEFT JOIN linea_referencia lr ON lr.linea_id = l.id AND lr.referencia_id = ref_j.id
--   linea_id / referencia_id en SELECT: COALESCE(lr.*, l.id / ref_j.id, cast fallback)

COMMENT ON VIEW public.v_stock_rimec IS
  'Catálogo web. 1 fila por ppd (DISTINCT ON). JOINs pilares con proveedor_id del PP. cajas_disponibles = cajas - vendidas.';
