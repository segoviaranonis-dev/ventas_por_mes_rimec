-- ============================================================================
-- BACKFILL: Corregir pedidos desincronizados
-- ACCIÓN: Cambiar PENDIENTE → CONFIRMADO cuando todas las FIs están CONFIRMADA
-- ============================================================================

-- PASO 1: VERIFICACIÓN (ejecutar primero para ver qué se va a cambiar)
SELECT
    pvr.id AS pedido_id,
    pvr.nro_pedido,
    pvr.estado AS estado_actual,
    'CONFIRMADO' AS nuevo_estado,
    COUNT(fi.id) AS total_fis,
    SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) AS fis_confirmadas,
    pvr.created_at
FROM pedido_venta_rimec pvr
INNER JOIN factura_interna fi ON fi.pedido_id = pvr.id
WHERE pvr.estado = 'PENDIENTE'
GROUP BY pvr.id, pvr.nro_pedido, pvr.estado, pvr.created_at
HAVING
    COUNT(fi.id) > 0
    AND SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) = COUNT(fi.id)
ORDER BY pvr.id;

-- PASO 2: BACKFILL (ejecutar solo después de verificar PASO 1)
-- IMPORTANTE: Esto es una corrección de datos históricos

WITH pedidos_a_confirmar AS (
    SELECT
        pvr.id AS pedido_id
    FROM pedido_venta_rimec pvr
    INNER JOIN factura_interna fi ON fi.pedido_id = pvr.id
    WHERE pvr.estado = 'PENDIENTE'
    GROUP BY pvr.id
    HAVING
        COUNT(fi.id) > 0
        AND SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) = COUNT(fi.id)
)
UPDATE pedido_venta_rimec pvr
SET estado = 'CONFIRMADO'
FROM pedidos_a_confirmar pac
WHERE pvr.id = pac.pedido_id
  AND pvr.estado = 'PENDIENTE'
RETURNING
    pvr.id,
    pvr.nro_pedido,
    pvr.estado;

-- PASO 3: VERIFICACIÓN POST-BACKFILL
-- Debe dar 0 filas si el backfill fue exitoso
SELECT
    pvr.id AS pedido_id,
    pvr.nro_pedido,
    pvr.estado,
    COUNT(fi.id) AS total_fis,
    STRING_AGG(DISTINCT fi.estado, ', ') AS estados_fis
FROM pedido_venta_rimec pvr
LEFT JOIN factura_interna fi ON fi.pedido_id = pvr.id
WHERE pvr.estado = 'PENDIENTE'
  AND EXISTS (
      SELECT 1 FROM factura_interna
      WHERE pedido_id = pvr.id
        AND estado = 'CONFIRMADA'
  )
GROUP BY pvr.id, pvr.nro_pedido, pvr.estado
HAVING
    COUNT(fi.id) > 0
    AND SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) = COUNT(fi.id);
