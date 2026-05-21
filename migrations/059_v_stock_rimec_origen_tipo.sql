-- Migración 059: Agregar columnas origen a v_stock_rimec
-- OT: OT-RIMEC-WEB-TARJETAS-MULTI-ORIGEN-001
-- Autor: Claude Code
-- Fecha: 2026-05-19
--
-- Objetivo: Exponer origen_tipo, deposito_id, clasificacion_stock_id en v_stock_rimec
-- para que frontend pueda agrupar tarjetas multi-origen (TRÁNSITO vs PRONTA ENTREGA).
--
-- Estado HOY: todas las filas son TRÁNSITO_PP (datos de pedido_proveedor).
-- Estado FUTURO: cuando exista stock_detalle con deposito_id, se mezclarán orígenes.

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 1: DROP vista existente (columnas incompatibles)
-- ══════════════════════════════════════════════════════════════════════════════

DROP VIEW IF EXISTS v_stock_rimec CASCADE;

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 2: Recrear vista v_stock_rimec con columnas de origen
-- ══════════════════════════════════════════════════════════════════════════════

CREATE VIEW v_stock_rimec AS
SELECT DISTINCT ON (ppd.id)
    ppd.id AS det_id,
    pp.id AS pp_id,
    pp.numero_registro AS pp_nro,
    COALESCE(pp.numero_proforma, '') AS proforma,
    (pp.fecha_arribo_estimada)::text AS eta,
    pp.estado AS pp_estado,
    ppd.id_marca::bigint AS marca_id,
    COALESCE(mv.descp_marca, '—') AS descp_marca,
    COALESCE(lr.linea_id, l.id, x.cast_linea_id)::bigint AS linea_id,
    COALESCE(lr.referencia_id, ref_j.id, x.cast_referencia_id)::bigint AS referencia_id,
    COALESCE(lr.grupo_estilo_id, x.cast_style_id)::bigint AS grupo_estilo_id,
    lr.tipo_1_id::bigint AS tipo_1_id,
    COALESCE(ppd.linea, '') AS linea_codigo,
    COALESCE(ppd.referencia, '') AS referencia_codigo,
    COALESCE(
        (COALESCE(lr.grupo_estilo_id, x.cast_style_id))::text,
        btrim(COALESCE(ppd.style_code::text, '')),
        ''
    ) AS style_code,
    COALESCE(ppd.nombre, '') AS nombre,
    COALESCE(ppd.material_code, '') AS material_code,
    COALESCE(ppd.descp_material, '') AS descp_material,
    COALESCE(ppd.color_code, '') AS color_code,
    COALESCE(ppd.descp_color, '') AS descp_color,
    col_j.hex_web AS color_hex,
    ppd.grades_json,
    COALESCE(ppd.cantidad_cajas, 0) AS cantidad_cajas,
    COALESCE(ppd.cantidad_pares, 0) AS cantidad_pares,
    COALESCE(ppd.pares_vendidos, 0) AS pares_vendidos,
    GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) AS saldo_pares,
    CASE
        WHEN COALESCE(ppd.cantidad_cajas, 0) > 0 THEN ppd.cantidad_pares / ppd.cantidad_cajas
        ELSE 0
    END AS pares_por_caja,
    GREATEST(
        0,
        COALESCE(ppd.cantidad_cajas, 0) - CASE
            WHEN COALESCE(ppd.cantidad_cajas, 0) > 0
             AND COALESCE(ppd.cantidad_pares, 0) > 0
            THEN (
                COALESCE(ppd.pares_vendidos, 0)
                + (ppd.cantidad_pares / ppd.cantidad_cajas)
                - 1
            ) / (ppd.cantidad_pares / ppd.cantidad_cajas)
            ELSE COALESCE(ppd.pares_vendidos, 0)
        END
    )::integer AS cajas_disponibles,
    ppd.unit_fob_ajustado,
    pl.lpn,
    pl.lpc02,
    pl.lpc03,
    pl.lpc04,
    pl.nombre_caso_aplicado AS caso_precio,
    l.caso_id AS caso_id,
    COALESCE(cpb.nombre_caso, '') AS descp_caso,
    COALESCE(lr.descp_grupo_estilo, ge.descp_grupo_estilo, '') AS descp_grupo_estilo,
    COALESCE(lr.descp_tipo_1, t1.descp_tipo_1, '') AS descp_tipo_1,
    CASE
        WHEN COALESCE(ppd.linea, '') <> ''
         AND COALESCE(ppd.referencia, '') <> ''
         AND COALESCE(ppd.material_code, '') <> ''
         AND COALESCE(ppd.color_code, '') <> ''
        THEN 'https://extrlcvcgypwazxipvqm.supabase.co/storage/v1/object/public/productos/'
             || ppd.linea || '-' || ppd.referencia || '-'
             || ppd.material_code || '-' || ppd.color_code || '.jpg'
        ELSE NULL
    END AS imagen_url,

    -- ═══════════════════════════════════════════════════════════════════════
    -- COLUMNAS NUEVAS: origen multi-tarjeta (OT-RIMEC-WEB-TARJETAS-MULTI-ORIGEN-001)
    -- ═══════════════════════════════════════════════════════════════════════

    -- HOY: todas las filas son TRÁNSITO_PP (pedido en camino)
    -- FUTURO: cuando exista stock_detalle.deposito_id, será 'STOCK_LOCAL'
    'TRÁNSITO_PP'::text AS origen_tipo,

    -- HOY: NULL (no hay stock físico en depósito)
    -- FUTURO: stock_detalle.deposito_id cuando la fila venga de inventario local
    NULL::bigint AS deposito_id,

    -- HOY: NULL (clasificación solo aplica a stock local)
    -- FUTURO: stock_detalle.clasificacion_stock_id (Normal/Oferta/Liquidación)
    NULL::bigint AS clasificacion_stock_id,

    -- Joins futuros para display (cuando stock local exista):
    NULL::text AS deposito_nombre,              -- deposito.nombre
    NULL::text AS clasificacion_stock_descp     -- clasificacion_stock.descripcion

FROM pedido_proveedor_detalle ppd
JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
LEFT JOIN material m
    ON m.codigo_proveedor::text = ppd.material_code
   AND m.proveedor_id = pp.proveedor_importacion_id
LEFT JOIN linea l
    ON l.codigo_proveedor::text = ppd.linea
   AND l.proveedor_id = pp.proveedor_importacion_id
LEFT JOIN caso_precio_biblioteca cpb ON cpb.id = l.caso_id
LEFT JOIN color col_j
    ON col_j.codigo_proveedor::text = ppd.color_code
   AND col_j.proveedor_id = pp.proveedor_importacion_id
   AND col_j.activo = TRUE
LEFT JOIN referencia ref_j
    ON ref_j.codigo_proveedor::text = ppd.referencia
   AND ref_j.linea_id = l.id
CROSS JOIN LATERAL (
    SELECT
        CASE
            WHEN nullif(btrim(ppd.linea::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.linea::text)::bigint
            ELSE NULL::bigint
        END AS cast_linea_id,
        CASE
            WHEN nullif(btrim(ppd.referencia::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.referencia::text)::bigint
            ELSE NULL::bigint
        END AS cast_referencia_id,
        CASE
            WHEN nullif(btrim(ppd.style_code::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.style_code::text)::bigint
            ELSE NULL::bigint
        END AS cast_style_id
) x
LEFT JOIN linea_referencia lr
    ON lr.linea_id = l.id
   AND lr.referencia_id = ref_j.id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = COALESCE(lr.grupo_estilo_id, x.cast_style_id)
LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
LEFT JOIN LATERAL (
    SELECT pl2.lpn, pl2.lpc02, pl2.lpc03, pl2.lpc04, pl2.nombre_caso_aplicado
    FROM precio_lista pl2
    WHERE pl2.evento_id = COALESCE(ic.precio_evento_id, (
        SELECT pe.id FROM precio_evento pe
        WHERE pe.estado = 'cerrado'
        ORDER BY pe.created_at DESC
        LIMIT 1
    ))
    AND pl2.linea_id = COALESCE(l.id, ref_j.linea_id)
    AND pl2.referencia_id = ref_j.id
    AND pl2.material_id = m.id
    LIMIT 1
) pl ON true
-- Catálogo = tránsito activo (no confundir con cierre de compra legal)
WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
  AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
ORDER BY ppd.id;

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 2: Comentarios sobre las nuevas columnas
-- ══════════════════════════════════════════════════════════════════════════════

COMMENT ON VIEW v_stock_rimec IS
  'Catálogo web RIMEC. Incluye columnas origen_tipo, deposito_id, clasificacion_stock_id para tarjetas multi-origen. HOY: solo TRÁNSITO_PP. FUTURO: STOCK_LOCAL cuando exista inventario físico.';

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 3: Verificación
-- ══════════════════════════════════════════════════════════════════════════════

DO $$
DECLARE
  v_count_transito INTEGER;
  v_count_stock_local INTEGER;
  v_etas_distintas INTEGER;
BEGIN
  SELECT COUNT(*) INTO v_count_transito
  FROM v_stock_rimec
  WHERE origen_tipo = 'TRÁNSITO_PP';

  SELECT COUNT(*) INTO v_count_stock_local
  FROM v_stock_rimec
  WHERE origen_tipo = 'STOCK_LOCAL';

  SELECT COUNT(DISTINCT eta) INTO v_etas_distintas
  FROM v_stock_rimec
  WHERE eta IS NOT NULL;

  RAISE NOTICE '[059] ✓ v_stock_rimec recreado con columnas origen';
  RAISE NOTICE '[059]   - Filas TRÁNSITO_PP: %', v_count_transito;
  RAISE NOTICE '[059]   - Filas STOCK_LOCAL: % (esperado 0 hoy)', v_count_stock_local;
  RAISE NOTICE '[059]   - ETAs distintas: % (agrupación multi-tarjeta)', v_etas_distintas;
END;
$$;

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 4: Instrucciones para fase STOCK_LOCAL (futuro)
-- ══════════════════════════════════════════════════════════════════════════════

-- Cuando exista tabla `stock_detalle` con (deposito_id, clasificacion_stock_id),
-- reemplazar la vista con UNION de dos fuentes:
--
-- CREATE OR REPLACE VIEW v_stock_rimec AS
-- (
--   -- TRÁNSITO_PP (pedidos en camino) — query actual
--   SELECT ..., 'TRÁNSITO_PP' AS origen_tipo, ...
--   FROM pedido_proveedor_detalle ppd ...
-- )
-- UNION ALL
-- (
--   -- STOCK_LOCAL (inventario físico en depósitos)
--   SELECT
--     sd.id AS det_id,
--     NULL AS pp_id,
--     NULL AS pp_nro,
--     '' AS proforma,
--     NULL AS eta,
--     ...
--     'STOCK_LOCAL'::text AS origen_tipo,
--     sd.deposito_id,
--     sd.clasificacion_stock_id,
--     d.nombre AS deposito_nombre,
--     cs.descripcion AS clasificacion_stock_descp
--   FROM stock_detalle sd
--   JOIN deposito d ON d.id = sd.deposito_id
--   LEFT JOIN clasificacion_stock cs ON cs.id = sd.clasificacion_stock_id
--   WHERE sd.cantidad_disponible > 0
-- )
