-- ═══════════════════════════════════════════════════════════════════════════
-- AUDITORÍA COMPLETA: Carrito del usuario Bzzf
-- ═══════════════════════════════════════════════════════════════════════════

-- ══════════════════════════════════════════════════════════════════════
-- 1. VENDEDOR: Verificar que Bzzf existe y es VENDEDOR
-- ══════════════════════════════════════════════════════════════════════
SELECT
    id_usuario,
    descp_usuario,
    categoria,
    rol_id,
    (SELECT nombre_rol FROM maestro_rol_acceso WHERE id = usuario_v2.rol_id) AS rol_nombre
FROM usuario_v2
WHERE descp_usuario ILIKE '%Bzzf%';

-- ══════════════════════════════════════════════════════════════════════
-- 2. SESIÓN ACTIVA: Verificar carrito_sesion de Bzzf
-- ══════════════════════════════════════════════════════════════════════
SELECT
    cs.id_usuario,
    u.descp_usuario AS vendedor,
    cs.cliente_id,
    cs.cliente_nombre,
    cs.lista_precio_id,
    (SELECT nombre FROM (VALUES (1, 'LPN'), (2, 'LPC02'), (3, 'LPC03'), (4, 'LPC04')) AS l(id, nombre) WHERE l.id = cs.lista_precio_id) AS lista_nombre,
    cs.descuentos AS descuentos_globales,
    cs.descuentos_lote,
    cs.iniciada_en,
    cs.actualizada_en,
    cs.validacion_estado,
    cs.validacion_token,
    cs.validada_en
FROM carrito_sesion cs
JOIN usuario_v2 u ON u.id_usuario = cs.id_usuario
WHERE u.descp_usuario ILIKE '%Bzzf%';

-- ══════════════════════════════════════════════════════════════════════
-- 3. ITEMS DEL CARRITO: Verificar carrito_item con JOIN a v_stock_rimec
-- ══════════════════════════════════════════════════════════════════════
SELECT
    ci.id_usuario,
    u.descp_usuario AS vendedor,
    ci.det_id,
    ci.pp_id,
    ci.cantidad_cajas,
    ci.precio_snapshot,
    ci.marca_snapshot,
    ci.caso_snapshot,
    -- Datos de v_stock_rimec (JOIN)
    vs.linea_codigo,
    vs.referencia_codigo,
    vs.descp_color,
    vs.cantidad_pares AS stock_total,
    vs.pares_vendidos AS stock_vendidos,
    vs.saldo_pares AS stock_disponible,
    vs.cajas_disponibles,
    -- PRECIOS de v_stock_rimec (LO CRÍTICO)
    vs.lpn AS precio_lpn,
    vs.lpc02 AS precio_lpc02,
    vs.lpc03 AS precio_lpc03,
    vs.lpc04 AS precio_lpc04,
    vs.descp_caso AS caso_actual,
    -- Validación
    CASE
        WHEN vs.det_id IS NULL THEN '⚠️ SKU NO EXISTE EN v_stock_rimec'
        WHEN vs.lpn IS NULL AND vs.lpc02 IS NULL AND vs.lpc03 IS NULL AND vs.lpc04 IS NULL THEN '⚠️ SIN PRECIOS'
        WHEN vs.cajas_disponibles < ci.cantidad_cajas THEN '⚠️ STOCK INSUFICIENTE'
        ELSE '✅ OK'
    END AS estado_validacion
FROM carrito_item ci
JOIN usuario_v2 u ON u.id_usuario = ci.id_usuario
LEFT JOIN v_stock_rimec vs ON vs.det_id = ci.det_id
WHERE u.descp_usuario ILIKE '%Bzzf%'
ORDER BY ci.det_id;

-- ══════════════════════════════════════════════════════════════════════
-- 4. RESUMEN: Totales y diagnóstico
-- ══════════════════════════════════════════════════════════════════════
SELECT
    COUNT(*) AS total_items_carrito,
    SUM(ci.cantidad_cajas) AS total_cajas,
    SUM(ci.cantidad_cajas * COALESCE(vs.pares_por_caja, 0)) AS total_pares_estimado,
    COUNT(CASE WHEN vs.det_id IS NULL THEN 1 END) AS items_sin_stock_data,
    COUNT(CASE WHEN vs.lpn IS NULL AND vs.lpc02 IS NULL AND vs.lpc03 IS NULL AND vs.lpc04 IS NULL THEN 1 END) AS items_sin_precios,
    COUNT(CASE WHEN vs.cajas_disponibles < ci.cantidad_cajas THEN 1 END) AS items_stock_insuficiente,
    COUNT(CASE WHEN vs.det_id IS NOT NULL AND vs.lpn IS NOT NULL THEN 1 END) AS items_ok
FROM carrito_item ci
JOIN usuario_v2 u ON u.id_usuario = ci.id_usuario
LEFT JOIN v_stock_rimec vs ON vs.det_id = ci.det_id
WHERE u.descp_usuario ILIKE '%Bzzf%';

-- ══════════════════════════════════════════════════════════════════════
-- 5. CONFIGURACIÓN DE FACTURAS: Verificar descuentos_lote
-- ══════════════════════════════════════════════════════════════════════
WITH facturas_config AS (
    SELECT
        cs.id_usuario,
        jsonb_array_elements(cs.descuentos_lote->'facturas') AS factura
    FROM carrito_sesion cs
    JOIN usuario_v2 u ON u.id_usuario = cs.id_usuario
    WHERE u.descp_usuario ILIKE '%Bzzf%'
)
SELECT
    factura->>'pp_id' AS pp_id,
    factura->>'marca' AS marca,
    factura->>'caso' AS caso,
    (factura->>'lista_precio_id')::int AS lista_precio_id,
    factura->'descuentos' AS descuentos,
    (factura->>'pre_autorizado')::boolean AS pre_autorizado,
    (factura->>'items_count')::int AS items_count
FROM facturas_config;

-- ══════════════════════════════════════════════════════════════════════
-- 6. DIAGNÓSTICO: Items con problemas específicos
-- ══════════════════════════════════════════════════════════════════════
SELECT
    'CRÍTICO: Items sin datos en v_stock_rimec' AS diagnostico,
    ci.det_id,
    ci.pp_id,
    ci.marca_snapshot,
    ci.caso_snapshot
FROM carrito_item ci
JOIN usuario_v2 u ON u.id_usuario = ci.id_usuario
LEFT JOIN v_stock_rimec vs ON vs.det_id = ci.det_id
WHERE u.descp_usuario ILIKE '%Bzzf%'
  AND vs.det_id IS NULL

UNION ALL

SELECT
    'ADVERTENCIA: Items sin precios' AS diagnostico,
    ci.det_id,
    ci.pp_id,
    ci.marca_snapshot,
    ci.caso_snapshot
FROM carrito_item ci
JOIN usuario_v2 u ON u.id_usuario = ci.id_usuario
LEFT JOIN v_stock_rimec vs ON vs.det_id = ci.det_id
WHERE u.descp_usuario ILIKE '%Bzzf%'
  AND vs.det_id IS NOT NULL
  AND vs.lpn IS NULL
  AND vs.lpc02 IS NULL
  AND vs.lpc03 IS NULL
  AND vs.lpc04 IS NULL;
