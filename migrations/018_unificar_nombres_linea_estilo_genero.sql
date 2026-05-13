-- 018 — Estándar global de nombres (línea, estilo, género, descripciones)
-- Ejecutar en Supabase después de 011 y de poblar linea.genero_id según maestro genero.
--
-- Resumen:
--   · v_stock_web: linea_id, referencia_id, grupo_estilo_id, descp_grupo_estilo, genero_id, descp_genero
--     (se eliminan alias estilo_id / estilo para el mismo concepto que v_stock_rimec).
--   · linea_caso: genero → descp_genero; estilo → descp_estilo; tipo_1..4 → descp_tipo_1..4 (si existen).
--   · linea: DROP COLUMN genero (texto legado) si existe — usar solo genero_id (FK maestro genero).
--   · producto_v2: columna linea → linea_id (si existe).
--   · pedido_web_detalle: ADD linea_id / referencia_id + backfill desde codigos y línea ya resuelta.

BEGIN;

-- Asegurar columna linea.genero_id antes de dropear texto genero (instalaciones antiguas).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'linea' AND column_name = 'genero_id'
  ) THEN
    ALTER TABLE public.linea ADD COLUMN genero_id bigint NULL;
  END IF;
END $$;

-- Catálogo web une estilo vía línea; si la columna no existía, se crea nullable.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'linea' AND column_name = 'grupo_estilo_id'
  ) THEN
    ALTER TABLE public.linea ADD COLUMN grupo_estilo_id bigint NULL;
  END IF;
END $$;

-- ── 1) Renombrar columnas en linea_caso (texto de apoyo = descp_*) ───────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'linea_caso' AND column_name = 'genero'
  ) THEN
    ALTER TABLE public.linea_caso RENAME COLUMN genero TO descp_genero;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'linea_caso' AND column_name = 'estilo'
  ) THEN
    ALTER TABLE public.linea_caso RENAME COLUMN estilo TO descp_estilo;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'linea_caso' AND column_name = 'tipo_1'
  ) THEN
    ALTER TABLE public.linea_caso RENAME COLUMN tipo_1 TO descp_tipo_1;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'linea_caso' AND column_name = 'tipo_2'
  ) THEN
    ALTER TABLE public.linea_caso RENAME COLUMN tipo_2 TO descp_tipo_2;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'linea_caso' AND column_name = 'tipo_3'
  ) THEN
    ALTER TABLE public.linea_caso RENAME COLUMN tipo_3 TO descp_tipo_3;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'linea_caso' AND column_name = 'tipo_4'
  ) THEN
    ALTER TABLE public.linea_caso RENAME COLUMN tipo_4 TO descp_tipo_4;
  END IF;
END $$;

-- ── 2) producto_v2: linea (bigint) → linea_id ─────────────────────────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'producto_v2' AND column_name = 'linea'
  ) THEN
    ALTER TABLE public.producto_v2 RENAME COLUMN linea TO linea_id;
  END IF;
END $$;

-- ── 3) pedido_web_detalle: IDs numéricos además de códigos texto ─────────────
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'pedido_web_detalle'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'pedido_web_detalle' AND column_name = 'linea_id'
    ) THEN
      ALTER TABLE public.pedido_web_detalle ADD COLUMN linea_id bigint;
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema = 'public' AND table_name = 'pedido_web_detalle' AND column_name = 'referencia_id'
    ) THEN
      ALTER TABLE public.pedido_web_detalle ADD COLUMN referencia_id bigint;
    END IF;
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'pedido_web_detalle'
  ) THEN
    UPDATE public.pedido_web_detalle d
    SET linea_id = l.id
    FROM public.linea l
    WHERE d.linea_id IS NULL
      AND l.proveedor_id = 654
      AND trim(both from d.linea_codigo::text) = trim(both from l.codigo_proveedor::text);

    UPDATE public.pedido_web_detalle d
    SET referencia_id = r.id
    FROM public.linea l
    JOIN public.referencia r
      ON r.linea_id = l.id
     AND r.proveedor_id = l.proveedor_id
    WHERE d.referencia_id IS NULL
      AND d.linea_id = l.id
      AND trim(both from d.referencia_codigo::text) = trim(both from r.codigo_proveedor::text);
  END IF;
END $$;

-- ── 4) linea: quitar columna texto genero (usar genero_id + maestro genero) ───
ALTER TABLE public.linea DROP COLUMN IF EXISTS genero;

-- ── 5) Vista catálogo web — mismos nombres que el contrato RIMEC ─────────────
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
LEFT JOIN marca_v2 mv  ON mv.id_marca = agg.id_marca_ref
LEFT JOIN genero gen   ON gen.id = l.genero_id;

COMMENT ON VIEW public.v_stock_web IS
'Catálogo web: linea_id/referencia_id (bigint), linea_codigo/referencia_codigo (texto), '
'grupo_estilo_id + descp_grupo_estilo, genero_id + descp_genero.';

COMMIT;
