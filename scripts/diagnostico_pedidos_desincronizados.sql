-- ============================================================================
-- DIAGNÓSTICO: Pedidos desincronizados en pedido_venta_rimec
-- PROBLEMA: Pedidos en PENDIENTE con TODAS sus FIs en CONFIRMADA
-- ============================================================================

-- 1. Pedidos PENDIENTE con todas sus FIs confirmadas (candidatos a backfill)
SELECT
    pvr.id AS pedido_id,
    pvr.nro_pedido,
    pvr.estado AS estado_pedido,
    pvr.created_at AS fecha_pedido,
    COUNT(fi.id) AS total_fis,
    SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) AS fis_confirmadas,
    SUM(CASE WHEN fi.estado = 'RESERVADA' THEN 1 ELSE 0 END) AS fis_reservadas,
    SUM(CASE WHEN fi.estado = 'ANULADA' THEN 1 ELSE 0 END) AS fis_anuladas,
    STRING_AGG(DISTINCT fi.estado, ', ') AS estados_fis
FROM pedido_venta_rimec pvr
LEFT JOIN factura_interna fi ON fi.pedido_id = pvr.id
WHERE pvr.estado = 'PENDIENTE'
  AND EXISTS (
      SELECT 1 FROM factura_interna
      WHERE pedido_id = pvr.id
  )
GROUP BY pvr.id, pvr.nro_pedido, pvr.estado, pvr.created_at
HAVING
    COUNT(fi.id) > 0
    AND SUM(CASE WHEN fi.estado = 'CONFIRMADA' THEN 1 ELSE 0 END) = COUNT(fi.id)
ORDER BY pvr.id;

-- 2. Resumen por estado de pedido
SELECT
    pvr.estado,
    COUNT(*) AS cantidad_pedidos,
    COUNT(DISTINCT fi.id) AS total_fis_asociadas
FROM pedido_venta_rimec pvr
LEFT JOIN factura_interna fi ON fi.pedido_id = pvr.id
GROUP BY pvr.estado
ORDER BY pvr.estado;

-- 3. Resumen por estado de FI
SELECT
    estado,
    COUNT(*) AS cantidad_fis
FROM factura_interna
GROUP BY estado
ORDER BY estado;

-- 4. Pedidos sin FIs (huérfanos)
SELECT
    pvr.id,
    pvr.nro_pedido,
    pvr.estado,
    pvr.created_at
FROM pedido_venta_rimec pvr
WHERE NOT EXISTS (
    SELECT 1 FROM factura_interna
    WHERE pedido_id = pvr.id
)
ORDER BY pvr.id;

-- 5. FIs sin pedido_id (huérfanas)
SELECT
    fi.id,
    fi.nro_factura,
    fi.estado,
    fi.created_at
FROM factura_interna fi
WHERE fi.pedido_id IS NULL
ORDER BY fi.id;
