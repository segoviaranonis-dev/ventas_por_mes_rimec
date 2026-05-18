-- OT-DIAG-001: Consultas de diagnóstico

-- 1. COUNT combinacion
SELECT 'combinacion_count' AS query, COUNT(*)::text AS resultado FROM combinacion
UNION ALL
-- 2. COUNT proveedor_web
SELECT 'proveedor_web_count' AS query, COUNT(*)::text AS resultado FROM proveedor_web
UNION ALL
-- 3. Columnas de combinacion
SELECT 'combinacion_columns' AS query, string_agg(column_name, ', ' ORDER BY ordinal_position) AS resultado
FROM information_schema.columns
WHERE table_name = 'combinacion'
UNION ALL
-- 4. Columnas de stock_bazar (si existe)
SELECT 'stock_bazar_columns' AS query,
       COALESCE(string_agg(column_name, ', ' ORDER BY ordinal_position), 'TABLA NO EXISTE') AS resultado
FROM information_schema.columns
WHERE table_name = 'stock_bazar';
