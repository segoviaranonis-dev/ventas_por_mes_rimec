-- Pegar en Supabase SQL Editor tras 052 + 053b + 054
-- (053 solo staging; si falló 053 por función, ignorar si 053b OK)

-- 1) Columnas *_aplicado en precio_lista
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'precio_lista'
  AND column_name LIKE '%aplicado%'
ORDER BY 1;

-- 2) Firma función (debe ser: bigint, numeric, text)
SELECT pg_get_function_result(p.oid) AS resultado
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proname = 'calcular_precio_lista_evento_sql';

-- 3) Staging existe
SELECT to_regclass('public.precio_lista_staging') AS staging_tabla;

-- 4) Pilares post-049 (ajustar esperados si tu entorno difiere)
SELECT 'linea' AS tabla, COUNT(*)::bigint AS n FROM linea
UNION ALL SELECT 'referencia', COUNT(*) FROM referencia
UNION ALL SELECT 'precio_evento', COUNT(*) FROM precio_evento
UNION ALL SELECT 'precio_lista_staging', COUNT(*) FROM precio_lista_staging;
