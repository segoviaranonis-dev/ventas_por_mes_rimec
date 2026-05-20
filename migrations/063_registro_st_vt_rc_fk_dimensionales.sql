-- =============================================================================
-- 063 · Retail — Agregar FKs dimensionales a registro_st_vt_rc_reposicion
--
-- Problema: migración 060 creó la tabla sin marca_id, genero_id, grupo_estilo_id,
--           tipo_1_id, linea_id, referencia_id que el frontend necesita para filtros.
-- Solución: ALTER TABLE + backfill desde linea/linea_referencia.
-- OT: OT-PILARES-LEYES-IMPORTACION-001
-- =============================================================================

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 1: Agregar columnas FK dimensionales
-- ══════════════════════════════════════════════════════════════════════════════

ALTER TABLE public.registro_st_vt_rc_reposicion
    ADD COLUMN IF NOT EXISTS linea_id bigint NULL,
    ADD COLUMN IF NOT EXISTS referencia_id bigint NULL,
    ADD COLUMN IF NOT EXISTS marca_id bigint NULL,
    ADD COLUMN IF NOT EXISTS genero_id bigint NULL,
    ADD COLUMN IF NOT EXISTS grupo_estilo_id bigint NULL,
    ADD COLUMN IF NOT EXISTS tipo_1_id bigint NULL;

COMMENT ON COLUMN public.registro_st_vt_rc_reposicion.linea_id IS
  'FK a linea (resuelto desde linea_codigo_proveedor)';
COMMENT ON COLUMN public.registro_st_vt_rc_reposicion.referencia_id IS
  'FK a referencia (resuelto desde referencia_codigo_proveedor + linea_id)';
COMMENT ON COLUMN public.registro_st_vt_rc_reposicion.marca_id IS
  'FK a marca_v2 (heredado desde linea)';
COMMENT ON COLUMN public.registro_st_vt_rc_reposicion.genero_id IS
  'FK a genero (heredado desde linea)';
COMMENT ON COLUMN public.registro_st_vt_rc_reposicion.grupo_estilo_id IS
  'FK a grupo_estilo_v2 (heredado desde linea_referencia o linea)';
COMMENT ON COLUMN public.registro_st_vt_rc_reposicion.tipo_1_id IS
  'FK a tipo_1 (heredado desde linea_referencia)';

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 2: Índices para performance en filtros
-- ══════════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_reposicion_linea_id
    ON public.registro_st_vt_rc_reposicion (linea_id) WHERE linea_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reposicion_referencia_id
    ON public.registro_st_vt_rc_reposicion (referencia_id) WHERE referencia_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reposicion_marca_id
    ON public.registro_st_vt_rc_reposicion (marca_id) WHERE marca_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reposicion_grupo_estilo_id
    ON public.registro_st_vt_rc_reposicion (grupo_estilo_id) WHERE grupo_estilo_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_reposicion_tipo_1_id
    ON public.registro_st_vt_rc_reposicion (tipo_1_id) WHERE tipo_1_id IS NOT NULL;

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 3: Backfill FKs desde filas existentes (1497 filas actuales)
-- ══════════════════════════════════════════════════════════════════════════════

DO $$
DECLARE
  v_updated INTEGER;
BEGIN
  -- Backfill linea_id desde linea por codigo_proveedor
  UPDATE public.registro_st_vt_rc_reposicion r
  SET linea_id = l.id
  FROM public.linea l
  WHERE r.linea_id IS NULL
    AND trim(both from r.linea_codigo_proveedor) ~ '^[0-9]+$'
    AND l.codigo_proveedor::text = trim(r.linea_codigo_proveedor);

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  RAISE NOTICE '[063] Backfill linea_id: % filas', v_updated;

  -- Backfill referencia_id desde referencia por linea_id + codigo_proveedor
  UPDATE public.registro_st_vt_rc_reposicion r
  SET referencia_id = ref.id
  FROM public.referencia ref
  WHERE r.referencia_id IS NULL
    AND r.linea_id IS NOT NULL
    AND trim(both from r.referencia_codigo_proveedor) ~ '^[0-9]+$'
    AND ref.linea_id = r.linea_id
    AND ref.codigo_proveedor::text = trim(r.referencia_codigo_proveedor);

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  RAISE NOTICE '[063] Backfill referencia_id: % filas', v_updated;

  -- Backfill marca_id, genero_id desde linea
  UPDATE public.registro_st_vt_rc_reposicion r
  SET
    marca_id = l.marca_id,
    genero_id = l.genero_id
  FROM public.linea l
  WHERE r.linea_id = l.id
    AND (r.marca_id IS NULL OR r.genero_id IS NULL);

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  RAISE NOTICE '[063] Backfill marca_id, genero_id desde linea: % filas', v_updated;

  -- Backfill grupo_estilo_id, tipo_1_id desde linea_referencia
  UPDATE public.registro_st_vt_rc_reposicion r
  SET
    grupo_estilo_id = COALESCE(lr.grupo_estilo_id, l.grupo_estilo_id),
    tipo_1_id = lr.tipo_1_id
  FROM public.linea_referencia lr
  JOIN public.linea l ON l.id = lr.linea_id
  WHERE r.linea_id = lr.linea_id
    AND r.referencia_id = lr.referencia_id
    AND (r.grupo_estilo_id IS NULL OR r.tipo_1_id IS NULL);

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  RAISE NOTICE '[063] Backfill grupo_estilo_id, tipo_1_id desde linea_referencia: % filas', v_updated;

  -- Backfill grupo_estilo_id desde linea si linea_referencia no tiene
  UPDATE public.registro_st_vt_rc_reposicion r
  SET grupo_estilo_id = l.grupo_estilo_id
  FROM public.linea l
  WHERE r.linea_id = l.id
    AND r.grupo_estilo_id IS NULL
    AND l.grupo_estilo_id IS NOT NULL;

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  RAISE NOTICE '[063] Backfill grupo_estilo_id desde linea (fallback): % filas', v_updated;
END;
$$;

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 4: Verificación
-- ══════════════════════════════════════════════════════════════════════════════

DO $$
DECLARE
  v_total INTEGER;
  v_con_linea INTEGER;
  v_con_referencia INTEGER;
  v_con_marca INTEGER;
  v_con_genero INTEGER;
  v_con_estilo INTEGER;
  v_con_tipo1 INTEGER;
BEGIN
  SELECT COUNT(*) INTO v_total FROM public.registro_st_vt_rc_reposicion;
  SELECT COUNT(*) INTO v_con_linea FROM public.registro_st_vt_rc_reposicion WHERE linea_id IS NOT NULL;
  SELECT COUNT(*) INTO v_con_referencia FROM public.registro_st_vt_rc_reposicion WHERE referencia_id IS NOT NULL;
  SELECT COUNT(*) INTO v_con_marca FROM public.registro_st_vt_rc_reposicion WHERE marca_id IS NOT NULL;
  SELECT COUNT(*) INTO v_con_genero FROM public.registro_st_vt_rc_reposicion WHERE genero_id IS NOT NULL;
  SELECT COUNT(*) INTO v_con_estilo FROM public.registro_st_vt_rc_reposicion WHERE grupo_estilo_id IS NOT NULL;
  SELECT COUNT(*) INTO v_con_tipo1 FROM public.registro_st_vt_rc_reposicion WHERE tipo_1_id IS NOT NULL;

  RAISE NOTICE '[063] ✓ Migración completada';
  RAISE NOTICE '[063]   Total filas: %', v_total;
  RAISE NOTICE '[063]   Con linea_id: % (%.1f%%)', v_con_linea, (v_con_linea::float / NULLIF(v_total, 0) * 100);
  RAISE NOTICE '[063]   Con referencia_id: % (%.1f%%)', v_con_referencia, (v_con_referencia::float / NULLIF(v_total, 0) * 100);
  RAISE NOTICE '[063]   Con marca_id: % (%.1f%%)', v_con_marca, (v_con_marca::float / NULLIF(v_total, 0) * 100);
  RAISE NOTICE '[063]   Con genero_id: % (%.1f%%)', v_con_genero, (v_con_genero::float / NULLIF(v_total, 0) * 100);
  RAISE NOTICE '[063]   Con grupo_estilo_id: % (%.1f%%)', v_con_estilo, (v_con_estilo::float / NULLIF(v_total, 0) * 100);
  RAISE NOTICE '[063]   Con tipo_1_id: % (%.1f%%)', v_con_tipo1, (v_con_tipo1::float / NULLIF(v_total, 0) * 100);
END;
$$;

-- ══════════════════════════════════════════════════════════════════════════════
-- NOTAS FINALES
-- ══════════════════════════════════════════════════════════════════════════════

-- Frontend report/ puede hacer SELECT origen_holding AS origen_tienda para compatibilidad.
-- Import futuro (st_vt_rc_import.py) debe persistir TODAS estas FKs desde resolve_retail_fks().
