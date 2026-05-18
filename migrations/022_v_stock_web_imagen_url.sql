-- ═══════════════════════════════════════════════════════════════════════════
-- 022 — v_stock_web: exponer imagen_url
--
-- Patrón confirmado por Héctor:
--   https://<proyecto>.supabase.co/storage/v1/object/public/productos/
--     <linea_codigo>-<referencia_codigo>-<material_code>-<color_code>.jpg
--
-- La URL base se toma como literal; si en el futuro cambia el proyecto Supabase,
-- se actualiza este COMMENT/CONSTANT (esta vista es la única referencia).
--
-- Si falta alguno de los 4 códigos, imagen_url queda NULL (front muestra
-- placeholder).
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
    mat.codigo_proveedor::text                  AS material_code,
    mat.descripcion                             AS material_descripcion,
    c.color_id,
    col.codigo_proveedor::text                  AS color_code,
    col.nombre                                  AS color_nombre,
    col.hex_web,
    CASE
        WHEN l.codigo_proveedor IS NOT NULL
         AND r.codigo_proveedor IS NOT NULL
         AND mat.codigo_proveedor IS NOT NULL
         AND col.codigo_proveedor IS NOT NULL
        THEN 'https://extrlcvcgypwazxipvqm.supabase.co/storage/v1/object/public/productos/'
             || l.codigo_proveedor::text || '-'
             || r.codigo_proveedor::text || '-'
             || mat.codigo_proveedor::text || '-'
             || col.codigo_proveedor::text || '.jpg'
        ELSE NULL
    END                                         AS imagen_url,
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
'imagen_url = bucket público "productos" con patrón linea-ref-mat-color.jpg.';

COMMIT;
