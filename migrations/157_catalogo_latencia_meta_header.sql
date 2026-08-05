-- MIG-157 · Latencia catálogo RIMEC Web (1+2+3)
-- 1) Índices CP + PPD saldo + pilares join
-- 2) rimec_catalogo_meta: 1 pase CTE (sin 8 escaneos)
-- 3) rimec_catalogo_header_meta: global + 4 géneros en 1 RPC
-- NO destruir vistas (MIG-156 PE intacta).

-- ── 1 · Índices ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pp_cp_catalog
  ON public.pedido_proveedor (id)
  WHERE (estado_transito)::text = 'EN_TRANSITO'
    AND COALESCE(categoria_id, 2) = 2;

CREATE INDEX IF NOT EXISTS idx_ppd_saldo_vendible
  ON public.pedido_proveedor_detalle (pedido_proveedor_id, id)
  WHERE GREATEST(0, COALESCE(cantidad_pares, 0) - COALESCE(pares_vendidos, 0)) > 0;

CREATE INDEX IF NOT EXISTS idx_linea_prov_codigo
  ON public.linea (proveedor_id, codigo_proveedor);

CREATE INDEX IF NOT EXISTS idx_color_prov_codigo
  ON public.color (proveedor_id, codigo_proveedor)
  WHERE activo = true;

CREATE INDEX IF NOT EXISTS idx_material_prov_codigo
  ON public.material (proveedor_id, codigo_proveedor);

CREATE INDEX IF NOT EXISTS idx_referencia_linea_codigo
  ON public.referencia (linea_id, codigo_proveedor);

-- ── 2 · rimec_catalogo_meta — base filtrada una vez ──────────────────────────
CREATE OR REPLACE FUNCTION public.rimec_catalogo_meta(
  p_es_pe boolean DEFAULT false,
  p_marca_id bigint DEFAULT NULL,
  p_linea_ids bigint[] DEFAULT NULL,
  p_grupo_estilo_id bigint DEFAULT NULL,
  p_tipo_ids bigint[] DEFAULT NULL,
  p_genero_codigo text DEFAULT NULL,
  p_ramo_tipo text DEFAULT NULL,
  p_deposito text DEFAULT NULL,
  p_quincena_ids bigint[] DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_result jsonb;
BEGIN
  IF p_es_pe THEN
    WITH base AS MATERIALIZED (
      SELECT
        v.marca_id,
        btrim(v.descp_marca) AS descp_marca,
        v.linea_id,
        btrim(v.linea_codigo) AS linea_codigo,
        v.grupo_estilo_id,
        btrim(v.descp_grupo_estilo) AS descp_grupo_estilo,
        v.tipo_1_id,
        btrim(v.descp_tipo_1) AS descp_tipo_1,
        upper(btrim(COALESCE(v.genero_codigo, ''))) AS genero_codigo,
        btrim(COALESCE(v.descp_genero, '')) AS descp_genero,
        btrim(v.descp_color) AS descp_color,
        btrim(v.color_tono_canon->>'etiqueta') AS tono_lbl
      FROM public.v_stock_pe_rimec v
      WHERE v.cajas_disponibles > 0
        AND (p_marca_id IS NULL OR v.marca_id = p_marca_id)
        AND (p_linea_ids IS NULL OR cardinality(p_linea_ids) IS NULL OR cardinality(p_linea_ids) = 0
             OR v.linea_id = ANY(p_linea_ids))
        AND (p_grupo_estilo_id IS NULL OR v.grupo_estilo_id = p_grupo_estilo_id)
        AND (p_tipo_ids IS NULL OR cardinality(p_tipo_ids) IS NULL OR cardinality(p_tipo_ids) = 0
             OR v.tipo_1_id = ANY(p_tipo_ids))
        AND (p_genero_codigo IS NULL OR btrim(p_genero_codigo) = ''
             OR upper(btrim(COALESCE(v.genero_codigo, ''))) = upper(btrim(p_genero_codigo)))
        AND (p_ramo_tipo IS NULL OR btrim(p_ramo_tipo) = '' OR v.ramo_tipo = p_ramo_tipo)
        AND (p_deposito IS NULL OR btrim(p_deposito) = '' OR v.deposito_nombre = p_deposito)
    )
    SELECT jsonb_build_object(
      'marcas', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', marca_id, 'label', descp_marca) ORDER BY descp_marca)
        FROM (SELECT DISTINCT marca_id, descp_marca FROM base WHERE descp_marca <> '') s
      ), '[]'::jsonb),
      'lineas', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', linea_id, 'label', linea_codigo) ORDER BY linea_codigo)
        FROM (SELECT DISTINCT linea_id, linea_codigo FROM base WHERE linea_id IS NOT NULL AND linea_codigo <> '') s
      ), '[]'::jsonb),
      'estilos', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', grupo_estilo_id, 'label', descp_grupo_estilo) ORDER BY descp_grupo_estilo)
        FROM (SELECT DISTINCT grupo_estilo_id, descp_grupo_estilo FROM base
              WHERE grupo_estilo_id IS NOT NULL AND descp_grupo_estilo <> '') s
      ), '[]'::jsonb),
      'tipos', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', tipo_1_id, 'label', descp_tipo_1) ORDER BY descp_tipo_1)
        FROM (SELECT DISTINCT tipo_1_id, descp_tipo_1 FROM base
              WHERE tipo_1_id IS NOT NULL AND descp_tipo_1 <> '') s
      ), '[]'::jsonb),
      'generos', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('codigo', genero_codigo, 'label', COALESCE(NULLIF(descp_genero, ''), genero_codigo)) ORDER BY genero_codigo)
        FROM (SELECT DISTINCT genero_codigo, descp_genero FROM base WHERE genero_codigo <> '') s
      ), '[]'::jsonb),
      'colores', COALESCE((
        SELECT jsonb_agg(descp_color ORDER BY descp_color)
        FROM (SELECT DISTINCT descp_color FROM base WHERE descp_color <> '') s
      ), '[]'::jsonb),
      'quincenas', '[]'::jsonb,
      'tonos', COALESCE((
        SELECT jsonb_agg(tono_lbl ORDER BY tono_lbl)
        FROM (SELECT DISTINCT tono_lbl FROM base WHERE tono_lbl IS NOT NULL AND tono_lbl <> '') s
      ), '[]'::jsonb)
    ) INTO v_result;
  ELSE
    WITH base AS MATERIALIZED (
      SELECT
        v.marca_id,
        btrim(v.descp_marca) AS descp_marca,
        v.linea_id,
        btrim(v.linea_codigo) AS linea_codigo,
        v.grupo_estilo_id,
        btrim(v.descp_grupo_estilo) AS descp_grupo_estilo,
        v.tipo_1_id,
        btrim(v.descp_tipo_1) AS descp_tipo_1,
        upper(btrim(COALESCE(v.genero_codigo, ''))) AS genero_codigo,
        btrim(COALESCE(v.descp_genero, '')) AS descp_genero,
        btrim(v.descp_color) AS descp_color,
        v.quincena_arribo_id,
        btrim(v.quincena_desc) AS quincena_desc,
        btrim(v.color_tono_canon->>'etiqueta') AS tono_lbl
      FROM public.v_stock_rimec v
      WHERE v.cajas_disponibles > 0
        AND v.origen_tipo = 'TRÁNSITO_PP'
        AND (p_marca_id IS NULL OR v.marca_id = p_marca_id)
        AND (p_linea_ids IS NULL OR cardinality(p_linea_ids) IS NULL OR cardinality(p_linea_ids) = 0
             OR v.linea_id = ANY(p_linea_ids))
        AND (p_grupo_estilo_id IS NULL OR v.grupo_estilo_id = p_grupo_estilo_id)
        AND (p_tipo_ids IS NULL OR cardinality(p_tipo_ids) IS NULL OR cardinality(p_tipo_ids) = 0
             OR v.tipo_1_id = ANY(p_tipo_ids))
        AND (p_genero_codigo IS NULL OR btrim(p_genero_codigo) = ''
             OR upper(btrim(COALESCE(v.genero_codigo, ''))) = upper(btrim(p_genero_codigo)))
        AND (p_quincena_ids IS NULL OR cardinality(p_quincena_ids) IS NULL OR cardinality(p_quincena_ids) = 0
             OR v.quincena_arribo_id = ANY(p_quincena_ids))
    )
    SELECT jsonb_build_object(
      'marcas', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', marca_id, 'label', descp_marca) ORDER BY descp_marca)
        FROM (SELECT DISTINCT marca_id, descp_marca FROM base WHERE descp_marca <> '') s
      ), '[]'::jsonb),
      'lineas', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', linea_id, 'label', linea_codigo) ORDER BY linea_codigo)
        FROM (SELECT DISTINCT linea_id, linea_codigo FROM base WHERE linea_id IS NOT NULL AND linea_codigo <> '') s
      ), '[]'::jsonb),
      'estilos', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', grupo_estilo_id, 'label', descp_grupo_estilo) ORDER BY descp_grupo_estilo)
        FROM (SELECT DISTINCT grupo_estilo_id, descp_grupo_estilo FROM base
              WHERE grupo_estilo_id IS NOT NULL AND descp_grupo_estilo <> '') s
      ), '[]'::jsonb),
      'tipos', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', tipo_1_id, 'label', descp_tipo_1) ORDER BY descp_tipo_1)
        FROM (SELECT DISTINCT tipo_1_id, descp_tipo_1 FROM base
              WHERE tipo_1_id IS NOT NULL AND descp_tipo_1 <> '') s
      ), '[]'::jsonb),
      'generos', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('codigo', genero_codigo, 'label', COALESCE(NULLIF(descp_genero, ''), genero_codigo)) ORDER BY genero_codigo)
        FROM (SELECT DISTINCT genero_codigo, descp_genero FROM base WHERE genero_codigo <> '') s
      ), '[]'::jsonb),
      'colores', COALESCE((
        SELECT jsonb_agg(descp_color ORDER BY descp_color)
        FROM (SELECT DISTINCT descp_color FROM base WHERE descp_color <> '') s
      ), '[]'::jsonb),
      'quincenas', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', quincena_arribo_id, 'label', quincena_desc) ORDER BY quincena_arribo_id)
        FROM (SELECT DISTINCT quincena_arribo_id, quincena_desc FROM base
              WHERE quincena_arribo_id IS NOT NULL AND quincena_desc <> '') s
      ), '[]'::jsonb),
      'tonos', COALESCE((
        SELECT jsonb_agg(tono_lbl ORDER BY tono_lbl)
        FROM (SELECT DISTINCT tono_lbl FROM base WHERE tono_lbl IS NOT NULL AND tono_lbl <> '') s
      ), '[]'::jsonb)
    ) INTO v_result;
  END IF;

  RETURN COALESCE(v_result, '{}'::jsonb);
END;
$$;

COMMENT ON FUNCTION public.rimec_catalogo_meta IS
  'Meta sidebar catálogo · MIG-157 CTE 1 pase (CP/PE)';

GRANT EXECUTE ON FUNCTION public.rimec_catalogo_meta(
  boolean, bigint, bigint[], bigint, bigint[], text, text, text, bigint[]
) TO anon, authenticated, service_role;

-- ── 3 · Header mega-menú — 1 escaneo CP ─────────────────────────────────────
CREATE OR REPLACE FUNCTION public.rimec_catalogo_header_meta()
RETURNS jsonb
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_result jsonb;
BEGIN
  WITH base AS MATERIALIZED (
    SELECT
      v.marca_id,
      btrim(v.descp_marca) AS descp_marca,
      v.linea_id,
      btrim(v.linea_codigo) AS linea_codigo,
      v.grupo_estilo_id,
      btrim(v.descp_grupo_estilo) AS descp_grupo_estilo,
      v.tipo_1_id,
      btrim(v.descp_tipo_1) AS descp_tipo_1,
      upper(btrim(COALESCE(v.genero_codigo, ''))) AS genero_codigo,
      btrim(COALESCE(v.descp_genero, '')) AS descp_genero
    FROM public.v_stock_rimec v
    WHERE v.cajas_disponibles > 0
      AND v.origen_tipo = 'TRÁNSITO_PP'
  ),
  agg AS (
    SELECT
      g.genero_codigo,
      jsonb_build_object(
        'marcas', COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', marca_id, 'label', descp_marca) ORDER BY descp_marca)
          FROM (SELECT DISTINCT b.marca_id, b.descp_marca FROM base b
                WHERE b.genero_codigo = g.genero_codigo AND b.descp_marca <> '') x
        ), '[]'::jsonb),
        'lineas', COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', linea_id, 'label', linea_codigo) ORDER BY linea_codigo)
          FROM (SELECT DISTINCT b.linea_id, b.linea_codigo FROM base b
                WHERE b.genero_codigo = g.genero_codigo AND b.linea_id IS NOT NULL AND b.linea_codigo <> '') x
        ), '[]'::jsonb),
        'estilos', COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', grupo_estilo_id, 'label', descp_grupo_estilo) ORDER BY descp_grupo_estilo)
          FROM (SELECT DISTINCT b.grupo_estilo_id, b.descp_grupo_estilo FROM base b
                WHERE b.genero_codigo = g.genero_codigo AND b.grupo_estilo_id IS NOT NULL AND b.descp_grupo_estilo <> '') x
        ), '[]'::jsonb),
        'tipos', COALESCE((
          SELECT jsonb_agg(jsonb_build_object('id', tipo_1_id, 'label', descp_tipo_1) ORDER BY descp_tipo_1)
          FROM (SELECT DISTINCT b.tipo_1_id, b.descp_tipo_1 FROM base b
                WHERE b.genero_codigo = g.genero_codigo AND b.tipo_1_id IS NOT NULL AND b.descp_tipo_1 <> '') x
        ), '[]'::jsonb)
      ) AS meta
    FROM (SELECT DISTINCT genero_codigo FROM base WHERE genero_codigo <> '') g
  )
  SELECT jsonb_build_object(
    'global', jsonb_build_object(
      'marcas', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', marca_id, 'label', descp_marca) ORDER BY descp_marca)
        FROM (SELECT DISTINCT marca_id, descp_marca FROM base WHERE descp_marca <> '') s
      ), '[]'::jsonb),
      'lineas', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', linea_id, 'label', linea_codigo) ORDER BY linea_codigo)
        FROM (SELECT DISTINCT linea_id, linea_codigo FROM base WHERE linea_id IS NOT NULL AND linea_codigo <> '') s
      ), '[]'::jsonb),
      'estilos', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', grupo_estilo_id, 'label', descp_grupo_estilo) ORDER BY descp_grupo_estilo)
        FROM (SELECT DISTINCT grupo_estilo_id, descp_grupo_estilo FROM base
              WHERE grupo_estilo_id IS NOT NULL AND descp_grupo_estilo <> '') s
      ), '[]'::jsonb),
      'tipos', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('id', tipo_1_id, 'label', descp_tipo_1) ORDER BY descp_tipo_1)
        FROM (SELECT DISTINCT tipo_1_id, descp_tipo_1 FROM base
              WHERE tipo_1_id IS NOT NULL AND descp_tipo_1 <> '') s
      ), '[]'::jsonb),
      'generos', COALESCE((
        SELECT jsonb_agg(jsonb_build_object('codigo', genero_codigo, 'label', COALESCE(NULLIF(descp_genero, ''), genero_codigo)) ORDER BY genero_codigo)
        FROM (SELECT DISTINCT genero_codigo, descp_genero FROM base WHERE genero_codigo <> '') s
      ), '[]'::jsonb),
      'colores', '[]'::jsonb,
      'quincenas', '[]'::jsonb,
      'tonos', '[]'::jsonb
    ),
    'secciones', COALESCE((
      SELECT jsonb_object_agg(genero_codigo, meta) FROM agg
    ), '{}'::jsonb)
  ) INTO v_result;

  RETURN COALESCE(v_result, '{}'::jsonb);
END;
$$;

COMMENT ON FUNCTION public.rimec_catalogo_header_meta() IS
  'Header mega-menú CP · 1 escaneo · MIG-157';

GRANT EXECUTE ON FUNCTION public.rimec_catalogo_header_meta() TO anon, authenticated, service_role;

NOTIFY pgrst, 'reload schema';
