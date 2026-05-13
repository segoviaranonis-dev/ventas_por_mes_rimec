-- ═══════════════════════════════════════════════════════════════════════════
-- 015 — Pilares referencia: diagnóstico, trasvase, cerraduras, linea_referencia
-- NO ejecutar ciego: revisar salida de cada bloque SELECT en staging.
-- Contexto: migración 004 ya definió
--   uq_referencia_proveedor_linea_codigo UNIQUE (proveedor_id, linea_id, codigo_proveedor)
-- La misión pide ADEMÁS analizar duplicados por (proveedor_id, codigo_proveedor)
-- y UNIQUE (codigo_proveedor, proveedor_id) — solo es viable si negocio garantiza
-- un único código de referencia por proveedor en todo el catálogo (todas las líneas).
-- ═══════════════════════════════════════════════════════════════════════════

-- ── A) DIAGNÓSTICO — duplicados par (proveedor, código) con distinta línea ──
-- Si max_linea <> min_linea, NO fusionar por par: son SKUs distintos bajo Beira Rio.

-- SELECT proveedor_id, codigo_proveedor,
--        COUNT(*) AS n,
--        COUNT(DISTINCT linea_id) AS lineas_distintas,
--        array_agg(id ORDER BY id) AS ids,
--        MAX(id) FILTER (WHERE true) AS id_mas_reciente
-- FROM referencia
-- GROUP BY proveedor_id, codigo_proveedor
-- HAVING COUNT(*) > 1
-- ORDER BY lineas_distintas DESC, n DESC;

-- ── B) MAPEO id_viejo → id_canónico (solo cuando es seguro) ───────────────
-- Criterio seguro: mismo proveedor_id, mismo codigo_proveedor, MISMO linea_id,
-- múltiples filas id (error histórico). id_canónico = MAX(id).
-- Criterio arriesgado (solo si Dirección confirma): distintas linea_id pero mismo
-- código proveedor = duplicado real; entonces fusionar y actualizar combinacion etc.

-- WITH dup_same_linea AS (
--   SELECT proveedor_id, linea_id, codigo_proveedor,
--          MAX(id) AS id_keep,
--          array_agg(id ORDER BY id) FILTER (WHERE id <> MAX(id) OVER w) AS ids_drop
--   FROM referencia
--   WINDOW w AS (PARTITION BY proveedor_id, linea_id, codigo_proveedor)
--   GROUP BY proveedor_id, linea_id, codigo_proveedor
--   HAVING COUNT(*) > 1
-- )
-- SELECT * FROM dup_same_linea;

-- Mapa id_old → id_keep (solo duplicados con UNA sola linea_id en el grupo — Ley de trazabilidad):
-- CREATE TEMP TABLE _ref_id_map AS
-- SELECT r.id AS id_old, g.id_keep AS id_new
-- FROM referencia r
-- JOIN (
--   SELECT proveedor_id, codigo_proveedor, MAX(id) AS id_keep
--   FROM referencia
--   GROUP BY proveedor_id, codigo_proveedor
--   HAVING COUNT(*) > 1 AND COUNT(DISTINCT linea_id) = 1
-- ) g ON g.proveedor_id = r.proveedor_id AND g.codigo_proveedor = r.codigo_proveedor
-- WHERE r.id <> g.id_keep;
--
-- Si HAVING COUNT(DISTINCT linea_id) > 1: fusionar por par es incorrecto; resolver a mano
-- (o reasignar códigos en proveedor) antes de UNIQUE global (proveedor_id, codigo_proveedor).

-- ── C) TRASVASE — tablas conocidas con referencia_id (ajustar según FKs reales) ──
-- Ejecutar en orden: hijos primero, luego DELETE referencia duplicados.
-- Usar id_new = MAX(id) por grupo acordado con negocio.

-- UPDATE precio_lista pl
-- SET referencia_id = m.id_new
-- FROM _ref_id_map m
-- WHERE pl.referencia_id = m.id_old;

-- UPDATE combinacion c
-- SET referencia_id = m.id_new
-- FROM _ref_id_map m
-- WHERE c.referencia_id = m.id_old
--   AND NOT EXISTS (
--     SELECT 1 FROM combinacion c2
--     WHERE c2.linea_id = c.linea_id
--       AND c2.referencia_id = m.id_new
--       AND c2.material_id = c.material_id
--       AND c2.color_id = c.color_id
--       AND c2.talla_id = c.talla_id
--       AND c2.id <> c.id
--   );
-- -- Si EXISTS: hay colisión de combinación → fusionar movimientos / precios de combinacion
-- -- en un solo id (fuera de alcance de este script; resolver manualmente).

-- UPDATE linea_referencia lr
-- SET referencia_id = m.id_new
-- FROM _ref_id_map m
-- WHERE lr.referencia_id = m.id_old
--   AND NOT EXISTS (
--     SELECT 1 FROM linea_referencia lr2
--     WHERE lr2.linea_id = lr.linea_id AND lr2.referencia_id = m.id_new
--   );
-- -- Si colisión en (linea_id, referencia_id): fusionar columnas lr y borrar duplicado lr.

-- -- Otras columnas a verificar con:
-- SELECT DISTINCT tc.table_name, kcu.column_name
-- FROM information_schema.table_constraints tc
-- JOIN information_schema.key_column_usage kcu
--   ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
-- JOIN information_schema.constraint_column_usage ccu
--   ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
-- WHERE tc.table_schema = 'public' AND tc.constraint_type = 'FOREIGN KEY'
--   AND ccu.table_name = 'referencia';

-- DELETE FROM referencia r
-- USING _ref_id_map m
-- WHERE r.id = m.id_old;

-- ── D) CERRADURAS ───────────────────────────────────────────────────────────
-- Opción 1 (recomendada si el negocio mantiene código único por línea, no global):
-- Ya existe en 004: UNIQUE (proveedor_id, linea_id, codigo_proveedor)
-- Verificar que el constraint siga presente; no duplicar nombre.

-- Opción 2 — solo si A) no quedan filas con mismo (proveedor_id, codigo_proveedor)
--    y distinto linea_id:
-- ALTER TABLE referencia
--   ADD CONSTRAINT uq_referencia_proveedor_codigo_global
--   UNIQUE (proveedor_id, codigo_proveedor);

-- linea_referencia: una fila por par línea–referencia
-- ALTER TABLE linea_referencia
--   DROP CONSTRAINT IF EXISTS uq_linea_referencia_linea_ref;
-- ALTER TABLE linea_referencia
--   ADD CONSTRAINT uq_linea_referencia_linea_ref
--   UNIQUE (linea_id, referencia_id);

-- ── E) POBLAR linea_referencia (estilo desde línea, alineado a v_stock_web / pilares) ──
-- La vista v_stock_rimec une estilo vía linea_referencia; si falta la fila lr, el estilo queda vacío.
-- Poblar huecos desde maestro referencia + estilo de línea (grupo_estilo_v2 vía linea.grupo_estilo_id).

-- INSERT INTO linea_referencia (linea_id, referencia_id, proveedor_id, grupo_estilo_id, tipo_1_id)
-- SELECT r.linea_id, r.id, r.proveedor_id, l.grupo_estilo_id, NULL::bigint
-- FROM referencia r
-- JOIN linea l ON l.id = r.linea_id
-- WHERE NOT EXISTS (
--   SELECT 1 FROM linea_referencia x
--   WHERE x.linea_id = r.linea_id AND x.referencia_id = r.id
-- )
-- ON CONFLICT DO NOTHING;
-- -- Ajustar lista de columnas NOT NULL reales de linea_referencia antes de ejecutar.

-- Variante “solo lo que circula en tránsito” (misma geometría que v_stock_rimec sin lr):
-- INSERT ... SELECT DISTINCT l.id, ref_j.id, ref_j.proveedor_id, l.grupo_estilo_id, NULL
-- FROM pedido_proveedor_detalle ppd
-- JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
-- JOIN linea l ON l.codigo_proveedor::text = ppd.linea
-- JOIN referencia ref_j
--   ON ref_j.codigo_proveedor::text = ppd.referencia
--  AND ref_j.linea_id = l.id
-- WHERE pp.estado = ANY (ARRAY['ABIERTO','ENVIADO'])
--   AND COALESCE(ppd.cantidad_pares, 0) > 0
--   AND NOT EXISTS (
--     SELECT 1 FROM linea_referencia x
--     WHERE x.linea_id = ref_j.linea_id AND x.referencia_id = ref_j.id
--   );

-- Fin plantilla — descomentar y envolver en BEGIN … COMMIT tras validar en staging.
