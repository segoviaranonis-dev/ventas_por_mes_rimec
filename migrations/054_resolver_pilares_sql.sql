-- ============================================================
-- MIGRACIÓN 054 — Resolución FK pilares set-based SQL
-- ============================================================
-- OT: OT-MOTOR-OPTIMIZADO-FINAL-001 (Fase B - OT-524)
-- Fecha: 2026-05-18
-- Objetivo: UPSERT masivo línea+referencia+material → devolver mapeo completo
--
-- Elimina loops Python en resolución FK (prefetch_materiales, provisionar_pilares)
-- ============================================================

-- Índices para optimizar lookups por (proveedor_id, codigo_proveedor)
-- Si ya existen por UNIQUE constraint, CREATE INDEX IF NOT EXISTS no hace nada
CREATE INDEX IF NOT EXISTS idx_linea_proveedor_codigo
  ON public.linea (proveedor_id, codigo_proveedor);

CREATE INDEX IF NOT EXISTS idx_referencia_proveedor_codigo
  ON public.referencia (proveedor_id, codigo_proveedor);

CREATE INDEX IF NOT EXISTS idx_material_proveedor_codigo
  ON public.material (proveedor_id, codigo_proveedor);

-- ============================================================
-- FUNCIÓN: resolver_pilares_sql
-- ============================================================
-- Entrada: arrays de códigos + descripciones
-- Salida: tabla con mapeo (codigo, id) para cada pilar
--
-- Estrategia:
--   1. UPSERT líneas (ON CONFLICT DO NOTHING)
--   2. UPSERT referencias (requiere linea_id, usa subquery)
--   3. UPSERT materiales
--   4. SELECT final con mapeo completo
-- ============================================================

CREATE OR REPLACE FUNCTION resolver_pilares_sql(
    p_proveedor_id bigint,
    p_linea_codes int[],
    p_ref_codes int[],
    p_ref_linea_codes int[],  -- códigos línea para cada ref (mismo tamaño que p_ref_codes)
    p_mat_codes int[],
    p_mat_descs text[]         -- descripciones material (mismo tamaño que p_mat_codes)
)
RETURNS TABLE(
    tipo text,
    codigo_proveedor int,
    pilar_id bigint,
    linea_id_ref bigint  -- solo para referencias (linea padre)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_start_time timestamptz;
    v_end_time   timestamptz;
BEGIN
    v_start_time := clock_timestamp();

    -- ============================================================
    -- 1. UPSERT líneas
    -- ============================================================
    IF p_linea_codes IS NOT NULL AND array_length(p_linea_codes, 1) > 0 THEN
        INSERT INTO linea (proveedor_id, codigo_proveedor, marca_id, genero_id)
        SELECT
            p_proveedor_id,
            unnest(p_linea_codes),
            NULL,  -- marca_id se asigna después si es necesario
            NULL   -- genero_id se asigna después si es necesario
        ON CONFLICT (proveedor_id, codigo_proveedor) DO NOTHING;
    END IF;

    -- ============================================================
    -- 2. UPSERT referencias
    -- ============================================================
    IF p_ref_codes IS NOT NULL AND array_length(p_ref_codes, 1) > 0 THEN
        -- Primero necesitamos resolver linea_id para cada referencia
        INSERT INTO referencia (proveedor_id, linea_id, codigo_proveedor)
        SELECT
            p_proveedor_id,
            l.id,
            r.codigo_ref
        FROM UNNEST(p_ref_codes, p_ref_linea_codes) AS r(codigo_ref, codigo_linea)
        INNER JOIN linea l ON l.proveedor_id = p_proveedor_id
                           AND l.codigo_proveedor = r.codigo_linea
        ON CONFLICT (proveedor_id, linea_id, codigo_proveedor) DO NOTHING;
    END IF;

    -- ============================================================
    -- 3. UPSERT materiales
    -- ============================================================
    IF p_mat_codes IS NOT NULL AND array_length(p_mat_codes, 1) > 0 THEN
        INSERT INTO material (proveedor_id, codigo_proveedor, descripcion)
        SELECT
            p_proveedor_id,
            m.codigo,
            COALESCE(m.descripcion, '')
        FROM UNNEST(p_mat_codes, p_mat_descs) AS m(codigo, descripcion)
        ON CONFLICT (proveedor_id, codigo_proveedor)
        DO UPDATE SET descripcion = EXCLUDED.descripcion
                  WHERE material.descripcion IS NULL OR material.descripcion = '';
    END IF;

    -- ============================================================
    -- 4. SELECT mapeo completo
    -- ============================================================

    -- Líneas
    RETURN QUERY
    SELECT
        'linea'::text,
        l.codigo_proveedor,
        l.id,
        NULL::bigint
    FROM linea l
    WHERE l.proveedor_id = p_proveedor_id
      AND l.codigo_proveedor = ANY(p_linea_codes);

    -- Referencias
    RETURN QUERY
    SELECT
        'referencia'::text,
        r.codigo_proveedor,
        r.id,
        r.linea_id
    FROM referencia r
    WHERE r.proveedor_id = p_proveedor_id
      AND r.codigo_proveedor = ANY(p_ref_codes);

    -- Materiales
    RETURN QUERY
    SELECT
        'material'::text,
        m.codigo_proveedor,
        m.id,
        NULL::bigint
    FROM material m
    WHERE m.proveedor_id = p_proveedor_id
      AND m.codigo_proveedor = ANY(p_mat_codes);

    v_end_time := clock_timestamp();

    -- Log de performance (opcional)
    RAISE NOTICE 'resolver_pilares_sql: % lineas, % refs, % mats en %ms',
        array_length(p_linea_codes, 1),
        array_length(p_ref_codes, 1),
        array_length(p_mat_codes, 1),
        EXTRACT(MILLISECONDS FROM (v_end_time - v_start_time));

    RETURN;
END;
$$;

-- Verificación
DO $$
BEGIN
  RAISE NOTICE 'Funcion resolver_pilares_sql creada';
  RAISE NOTICE 'Indices (proveedor_id, codigo_proveedor) verificados/creados';
  RAISE NOTICE 'Uso: SELECT * FROM resolver_pilares_sql(proveedor_id, arrays...)';
END $$;
