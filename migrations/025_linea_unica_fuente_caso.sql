-- ═══════════════════════════════════════════════════════════════════════════
-- 025 — linea como ÚNICA fuente de verdad para Caso, Marca, Género y
--       clasificación (estilo/tipo). Elimina la tabla espejo linea_caso.
--
-- Decisión de diseño (Héctor):
--   "Asignar los casos a la tabla linea de manera tal sea la única fuente
--    de verdad para las consultas". El albañil anterior duplicó la asignación
--    en linea_caso (espejo) — la eliminamos.
--
-- Cambios:
--   · linea  +  caso_id      bigint  FK → caso_precio_biblioteca(id)
--   · linea  +  descp_estilo text
--   · linea  +  descp_tipo_1..4 text
--   · linea  −  caso_nombre  (texto, hoy NULL en las 1456 filas)
--   · DROP   linea_caso                   (espejo redundante)
--   · DROP   caso_precio_biblioteca_linea (nunca usada)
--   · DROP/recrea v_stock_web (depende de linea)
--   · DROP v_stock_rimec (se recrea desde scripts/fix_v_stock_rimec.py)
--
-- Como linea_caso hoy tiene 0 filas, no se pierde información operativa.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1) Sanity: verificar que linea_caso esté vacía antes del DROP ───────────
DO $$
DECLARE
    n_lc bigint;
BEGIN
    IF to_regclass('public.linea_caso') IS NOT NULL THEN
        SELECT COUNT(*) INTO n_lc FROM public.linea_caso;
        IF n_lc > 0 THEN
            RAISE EXCEPTION 'ABORTO: linea_caso tiene % filas. Migrá los datos a linea antes de continuar.', n_lc;
        END IF;
        RAISE NOTICE '✓ linea_caso vacía (0 filas), seguro para DROP';
    END IF;
END $$;

-- ── 2) Ampliar linea: nuevas columnas ──────────────────────────────────────
ALTER TABLE public.linea
    ADD COLUMN IF NOT EXISTS caso_id      bigint NULL,
    ADD COLUMN IF NOT EXISTS descp_estilo text   NULL,
    ADD COLUMN IF NOT EXISTS descp_tipo_1 text   NULL,
    ADD COLUMN IF NOT EXISTS descp_tipo_2 text   NULL,
    ADD COLUMN IF NOT EXISTS descp_tipo_3 text   NULL,
    ADD COLUMN IF NOT EXISTS descp_tipo_4 text   NULL;

-- FK explícita en pasada separada (ADD IF NOT EXISTS no aplica a constraints
-- antes de PG 17). Wrapping en DO para idempotencia.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'linea_caso_id_fkey'
    ) THEN
        ALTER TABLE public.linea
            ADD CONSTRAINT linea_caso_id_fkey
            FOREIGN KEY (caso_id) REFERENCES public.caso_precio_biblioteca(id)
            ON UPDATE CASCADE ON DELETE SET NULL;
        RAISE NOTICE '✓ FK linea.caso_id → caso_precio_biblioteca(id) creada';
    ELSE
        RAISE NOTICE '✓ FK linea_caso_id_fkey ya existía';
    END IF;
END $$;

-- Índice de soporte
CREATE INDEX IF NOT EXISTS idx_linea_caso_id ON public.linea(caso_id);

-- ── 3) Drop columna obsoleta linea.caso_nombre (texto NULL en 1456 filas) ──
ALTER TABLE public.linea DROP COLUMN IF EXISTS caso_nombre;

-- ── 4) Drop vistas dependientes (se recrean abajo / por script) ────────────
DROP VIEW IF EXISTS public.v_stock_web   CASCADE;
DROP VIEW IF EXISTS public.v_stock_rimec CASCADE;

-- ── 5) Drop tablas redundantes ─────────────────────────────────────────────
DROP TABLE IF EXISTS public.linea_caso                   CASCADE;
DROP TABLE IF EXISTS public.caso_precio_biblioteca_linea CASCADE;

-- ── 6) Recrear v_stock_web con caso_id + descp_caso ────────────────────────
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
    -- NUEVO: caso conceptual asignado a la línea (fuente: linea.caso_id)
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
'Catálogo web: linea_id/referencia_id (bigint), linea_codigo/referencia_codigo (texto), '
'grupo_estilo_id + descp_grupo_estilo, genero_id + descp_genero (bigint), '
'caso_id + descp_caso (bigint + texto, desde linea.caso_id → caso_precio_biblioteca). '
'imagen_url = bucket público "productos" con patrón linea-ref-mat-color.jpg.';

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN
-- ═══════════════════════════════════════════════════════════════════════════
SELECT 'linea_caso (debe ser NULL = tabla borrada)'  AS check, to_regclass('public.linea_caso')::text  AS valor UNION ALL
SELECT 'caso_precio_biblioteca_linea (debe ser NULL)',         to_regclass('public.caso_precio_biblioteca_linea')::text UNION ALL
SELECT 'linea.caso_id existe (debe ser bigint)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='caso_id') UNION ALL
SELECT 'linea.descp_estilo existe (debe ser text)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='descp_estilo') UNION ALL
SELECT 'linea.caso_nombre NO existe (debe ser NULL)',
       (SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name='linea' AND column_name='caso_nombre') UNION ALL
SELECT 'FK linea.caso_id → caso_precio_biblioteca',
       (SELECT pg_get_constraintdef(c.oid)
        FROM pg_constraint c WHERE c.conname='linea_caso_id_fkey') UNION ALL
SELECT 'v_stock_web existe (debe ser VIEW)',
       (SELECT 'VIEW' FROM information_schema.views
        WHERE table_schema='public' AND table_name='v_stock_web');

-- Conteo:
SELECT
    (SELECT COUNT(*) FROM public.linea WHERE activo=true)            AS lineas_activas,
    (SELECT COUNT(*) FROM public.linea WHERE caso_id IS NOT NULL)    AS lineas_con_caso_asignado,
    (SELECT COUNT(*) FROM public.caso_precio_biblioteca)             AS casos_biblioteca,
    (SELECT COUNT(*) FROM public.v_stock_web)                        AS filas_v_stock_web;
