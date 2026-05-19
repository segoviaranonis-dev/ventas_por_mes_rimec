-- 056 — Nomenclatura P0: alias canónicos en v_stock_web + rename staging retail
-- Ejecutar en Supabase antes del flujo comercial.
-- Mantiene columnas legacy (linea_codigo, linea_code…) para no romper deploys en vuelo.

BEGIN;

-- ── 1) v_stock_web: alias P0 (mismo valor que legacy) ─────────────────────
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
-- Columnas 1–26: mismo orden que migración 026 (CREATE OR REPLACE no permite reordenar).
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
    COALESCE(gen.descripcion, gen.codigo, '')   AS descp_genero,
    l.caso_id                                   AS caso_id,
    COALESCE(cpb.nombre_caso, '')               AS descp_caso,
    -- 27–30: alias P0 (solo al final; misma expresión que legacy)
    l.codigo_proveedor::text                    AS linea_codigo_proveedor,
    r.codigo_proveedor::text                    AS referencia_codigo_proveedor,
    mat.codigo_proveedor::text                  AS material_codigo_proveedor,
    col.codigo_proveedor::text                  AS color_codigo_proveedor
FROM mov_agg agg
JOIN combinacion c     ON c.id   = agg.combinacion_id
JOIN linea l           ON l.id   = c.linea_id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = l.grupo_estilo_id
JOIN referencia r      ON r.id   = c.referencia_id
LEFT JOIN material mat ON mat.id = c.material_id
LEFT JOIN color col    ON col.id = c.color_id
JOIN talla tl          ON tl.id  = c.talla_id
LEFT JOIN marca_v2 mv  ON mv.id_marca = COALESCE(agg.id_marca_ref, l.marca_id)
LEFT JOIN genero gen   ON gen.id = l.genero_id
LEFT JOIN caso_precio_biblioteca cpb ON cpb.id = l.caso_id;

COMMENT ON VIEW public.v_stock_web IS
'Catálogo web P0: linea_id + linea_codigo_proveedor (alias linea_codigo legacy). '
'Misma regla para referencia/material/color.';

-- ── 2) retail_multitienda_staging: rename códigos proveedor ───────────────
ALTER TABLE public.retail_multitienda_staging
    DROP COLUMN IF EXISTS sku_key;

DROP INDEX IF EXISTS public.idx_retail_staging_linea_ref;

ALTER TABLE public.retail_multitienda_staging
    RENAME COLUMN linea_code TO linea_codigo_proveedor;

ALTER TABLE public.retail_multitienda_staging
    RENAME COLUMN referencia_code TO referencia_codigo_proveedor;

ALTER TABLE public.retail_multitienda_staging
    ADD COLUMN sku_key text GENERATED ALWAYS AS (
        trim(both ' ' from linea_codigo_proveedor) || '|'
        || trim(both ' ' from referencia_codigo_proveedor)
        || '|' || material_id::text || '|' || color_id::text
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_retail_staging_linea_ref
    ON public.retail_multitienda_staging (linea_codigo_proveedor, referencia_codigo_proveedor);

COMMENT ON COLUMN public.retail_multitienda_staging.linea_codigo_proveedor IS
    'Código numérico proveedor (Excel columna Linea). P0 — antes linea_code.';
COMMENT ON COLUMN public.retail_multitienda_staging.referencia_codigo_proveedor IS
    'Código numérico proveedor (Excel columna Referencia). P0 — antes referencia_code.';

COMMIT;
