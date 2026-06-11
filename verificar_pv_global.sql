-- VERIFICAR: ¿La migración 107 se aplicó correctamente?

-- 1. ¿Existe la columna pv_global?
SELECT
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_name = 'factura_interna'
  AND column_name = 'pv_global';

-- 2. ¿Cuántas FIs tienen pv_global asignado?
SELECT
  estado,
  COUNT(*) as total,
  COUNT(pv_global) as con_pv_global,
  MIN(pv_global) as min_pv,
  MAX(pv_global) as max_pv
FROM factura_interna
GROUP BY estado
ORDER BY estado;

-- 3. Ver las últimas 10 FIs con su pv_global
SELECT
  id,
  nro_factura as legacy_nro,
  pv_global,
  'PV' || LPAD(pv_global::TEXT, 6, '0') as formato_correcto,
  estado,
  created_at
FROM factura_interna
WHERE pv_global IS NOT NULL
ORDER BY pv_global DESC
LIMIT 10;

-- 4. ¿Existen FIs CONFIRMADAS sin pv_global? (ERROR)
SELECT
  id,
  nro_factura,
  pv_global,
  estado,
  created_at
FROM factura_interna
WHERE estado = 'CONFIRMADA'
  AND pv_global IS NULL
ORDER BY created_at DESC
LIMIT 5;

-- 5. ¿Existe el trigger asignar_pv_global?
SELECT
  trigger_name,
  event_manipulation,
  action_timing
FROM information_schema.triggers
WHERE event_object_table = 'factura_interna'
  AND trigger_name = 'trigger_asignar_pv_global';