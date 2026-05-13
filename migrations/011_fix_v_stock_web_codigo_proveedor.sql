-- Migración 011: Agregar material_code y color_code a v_stock_web
-- Fecha: 2026-05-07
-- Problema: v_stock_web no expone codigo_proveedor de material y color
--           necesarios para construir URL de imagen en bazzar-web
-- URL correcta: {linea_codigo}-{referencia_codigo}-{material_code}-{color_code}.jpg

BEGIN;

DROP VIEW IF EXISTS v_stock_web;

CREATE OR REPLACE VIEW v_stock_web AS
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
            SELECT (tj->>'id_marca')::int
            FROM traspaso t
            JOIN traspaso_detalle td ON td.traspaso_id = t.id
            CROSS JOIN LATERAL jsonb_array_elements(t.snapshot_json) tj
            WHERE td.combinacion_id = md.combinacion_id
              AND t.almacen_destino_id = 1
              AND t.estado = 'CONFIRMADO'
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
    l.codigo_proveedor                          AS linea_codigo,
    l.descripcion                               AS linea_descripcion,
    r.codigo_proveedor                          AS referencia_codigo,
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
    COALESCE(ge.descp_grupo_estilo, '')         AS estilo,
    ge.id_grupo_estilo                          AS estilo_id
FROM mov_agg agg
JOIN combinacion c     ON c.id   = agg.combinacion_id
JOIN linea l           ON l.id   = c.linea_id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = l.grupo_estilo_id
JOIN referencia r      ON r.id   = c.referencia_id
LEFT JOIN material mat ON mat.id = c.material_id
LEFT JOIN color col    ON col.id = c.color_id
JOIN talla tl          ON tl.id  = c.talla_id
LEFT JOIN marca_v2 mv  ON mv.id_marca = agg.id_marca_ref;

COMMIT;
