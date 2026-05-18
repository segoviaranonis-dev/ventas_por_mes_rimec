-- ═══════════════════════════════════════════════════════════════════════════
-- 021 — Fix v_stock_web: leer id_marca desde la RAÍZ del snapshot_json
--
-- El snapshot_json es un objeto:
--   { id_pp, items:[...], id_marca, numero_factura }
--
-- La 018/019 usaban jsonb_array_elements(snapshot_json) → ERROR 22023
-- ("cannot extract elements from an object"). Acá lo leemos directo:
--   snapshot_json ->> 'id_marca'
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

DROP VIEW IF EXISTS public.v_stock_web;

CREATE OR REPLACE VIEW public.v_stock_web AS
WITH mov_agg AS (
    SELECT
        md.combinacion_id,
        sum(
            CASE
                WHEN m.tipo = 'INGRESO_COMPRA' AND m.almacen_destino_id = 1 THEN md.cantidad * md.signo
                WHEN m.tipo = 'VENTA_WEB'      AND m.almacen_origen_id  = 1 THEN -md.cantidad
                ELSE 0
            END
        ) AS stock_web,
        (
            SELECT NULLIF(t.snapshot_json ->> 'id_marca', '')::int
            FROM traspaso t
            JOIN traspaso_detalle td ON td.traspaso_id = t.id
            WHERE td.combinacion_id = md.combinacion_id
              AND t.almacen_destino_id = 1
              AND t.estado = 'CONFIRMADO'
              AND t.snapshot_json IS NOT NULL
              AND jsonb_typeof(t.snapshot_json) = 'object'
            ORDER BY t.id DESC
            LIMIT 1
        ) AS id_marca_ref
    FROM movimiento m
    JOIN movimiento_detalle md ON md.movimiento_id = m.id
    WHERE (
        (m.tipo = 'INGRESO_COMPRA' AND m.almacen_destino_id = 1) OR
        (m.tipo = 'VENTA_WEB'      AND m.almacen_origen_id  = 1)
    ) AND (
        m.tipo = 'VENTA_WEB' OR EXISTS (
            SELECT 1 FROM traspaso t
            JOIN traspaso_detalle td ON td.traspaso_id = t.id
            WHERE t.numero_registro = m.documento_ref
              AND td.combinacion_id = md.combinacion_id
              AND t.almacen_destino_id = 1
              AND t.estado = 'CONFIRMADO'
        )
    )
    GROUP BY md.combinacion_id
    HAVING sum(
        CASE
            WHEN m.tipo = 'INGRESO_COMPRA' AND m.almacen_destino_id = 1 THEN md.cantidad * md.signo
            WHEN m.tipo = 'VENTA_WEB'      AND m.almacen_origen_id  = 1 THEN -md.cantidad
            ELSE 0
        END
    ) > 0
)
SELECT
    c.id                                        AS combinacion_id,
    COALESCE(mv.descp_marca, '—')               AS marca,
    l.id                                        AS linea_id,
    l.codigo_proveedor::text                    AS linea_codigo,
    r.id                                        AS referencia_id,
    l.descripcion                               AS linea_descripcion,
    r.codigo_proveedor::text                    AS referencia_codigo,
    r.descripcion                               AS referencia_descripcion,
    c.material_id,
    mat.codigo_proveedor                        AS material_code,
    mat.descripcion                             AS material_descripcion,
    c.color_id,
    col.codigo_proveedor                        AS color_code,
    col.nombre                                  AS color_nombre,
    col.hex_web,
    (
        SELECT ppd.id_material FROM pedido_proveedor_detalle ppd
        WHERE ppd.linea      = l.codigo_proveedor::text
          AND ppd.referencia = r.codigo_proveedor::text
          AND ppd.descp_material = mat.descripcion
          AND ppd.id_material IS NOT NULL
        LIMIT 1
    )                                           AS id_material_f9,
    (
        SELECT ppd.id_color FROM pedido_proveedor_detalle ppd
        WHERE ppd.linea      = l.codigo_proveedor::text
          AND ppd.referencia = r.codigo_proveedor::text
          AND ppd.descp_color = col.nombre
          AND ppd.id_color IS NOT NULL
        LIMIT 1
    )                                           AS id_color_f9,
    tl.talla_etiqueta                           AS talla_codigo,
    tl.orden_visual                             AS talla_orden,
    agg.stock_web,
    NULL::numeric                               AS precio_web,
    COALESCE(ge.descp_grupo_estilo, '')         AS descp_grupo_estilo,
    ge.id_grupo_estilo                          AS grupo_estilo_id,
    l.genero_id                                 AS genero_id,
    COALESCE(gen.descripcion, gen.codigo, '')   AS descp_genero
FROM mov_agg agg
JOIN combinacion c     ON c.id   = agg.combinacion_id
JOIN linea l           ON l.id   = c.linea_id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = l.grupo_estilo_id
JOIN referencia r      ON r.id   = c.referencia_id
LEFT JOIN material mat ON mat.id = c.material_id
LEFT JOIN color col    ON col.id = c.color_id
JOIN talla tl          ON tl.id  = c.talla_id
LEFT JOIN marca_v2 mv  ON mv.id_marca = COALESCE(agg.id_marca_ref, l.marca_id)
LEFT JOIN genero gen   ON gen.id = l.genero_id;

COMMENT ON VIEW public.v_stock_web IS
'Catálogo web: linea_id/referencia_id (bigint), linea_codigo/referencia_codigo (texto), '
'grupo_estilo_id + descp_grupo_estilo, genero_id + descp_genero (bigint). '
'id_marca tomado del snapshot_json (objeto) del traspaso CONFIRMADO; fallback a linea.marca_id.';

COMMIT;
