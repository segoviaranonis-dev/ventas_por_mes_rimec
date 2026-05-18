-- ═══════════════════════════════════════════════════════════════════════════
-- 026 — Purga de atributos visuales de linea
--
-- Decisión de Héctor:
--   "Los Tipos y Estilo pertenecen exclusivamente a la relación
--    linea_referencia. La línea pura solo debe gestionar:
--    ID + Descripción + Marca (FK) + Género (FK) + Caso (FK)."
--
-- Cambios:
--   · linea  −  descp_estilo
--   · linea  −  descp_tipo_1, descp_tipo_2, descp_tipo_3, descp_tipo_4
--   · Recrea v_stock_web SIN esas columnas (no las exponía igual, pero
--     re-emitimos para consistencia y para que CASCADE no afecte).
--
-- Las columnas estaban en NULL en las 1456 líneas (introducidas en 025 y
-- nunca pobladas), por lo que no se pierde dato.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- Drop vistas que podrían depender (defensivo). Las recreamos abajo.
DROP VIEW IF EXISTS public.v_stock_web   CASCADE;
DROP VIEW IF EXISTS public.v_stock_rimec CASCADE;

ALTER TABLE public.linea
    DROP COLUMN IF EXISTS descp_estilo,
    DROP COLUMN IF EXISTS descp_tipo_1,
    DROP COLUMN IF EXISTS descp_tipo_2,
    DROP COLUMN IF EXISTS descp_tipo_3,
    DROP COLUMN IF EXISTS descp_tipo_4;

-- Recrear v_stock_web (igual que en 025, sin las columnas dropeadas)
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
    COALESCE(gen.descripcion, gen.codigo, '')   AS descp_genero,
    l.caso_id                                   AS caso_id,
    COALESCE(cpb.nombre_caso, '')               AS descp_caso
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
'Catálogo web tras 026: linea_id/referencia_id + linea_codigo/referencia_codigo + '
'grupo_estilo_id/descp_grupo_estilo (desde grupo_estilo_v2) + genero_id/descp_genero '
'(desde genero) + caso_id/descp_caso (desde linea.caso_id → caso_precio_biblioteca). '
'Estilo y Tipo de fila NUNCA salen de linea — siempre de linea_referencia.';

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN
-- ═══════════════════════════════════════════════════════════════════════════
SELECT 'linea.descp_estilo (debe ser NULL = dropeada)'   AS check,
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='descp_estilo') AS valor UNION ALL
SELECT 'linea.descp_tipo_1 (debe ser NULL)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='descp_tipo_1') UNION ALL
SELECT 'linea.descp_tipo_2 (debe ser NULL)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='descp_tipo_2') UNION ALL
SELECT 'linea.descp_tipo_3 (debe ser NULL)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='descp_tipo_3') UNION ALL
SELECT 'linea.descp_tipo_4 (debe ser NULL)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='descp_tipo_4') UNION ALL
SELECT 'linea.caso_id (debe seguir siendo bigint)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='caso_id') UNION ALL
SELECT 'linea.marca_id (debe seguir siendo bigint)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='marca_id') UNION ALL
SELECT 'linea.genero_id (debe seguir siendo bigint)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='genero_id') UNION ALL
SELECT 'v_stock_web (debe ser VIEW)',
       (SELECT 'VIEW' FROM information_schema.views
        WHERE table_schema='public' AND table_name='v_stock_web');

-- Columnas finales de linea (lista limpia)
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema='public' AND table_name='linea'
ORDER BY ordinal_position;
