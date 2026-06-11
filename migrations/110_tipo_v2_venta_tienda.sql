-- Migración 110: Agregar tipo_v2 para Sistema "Venta en Tienda"
-- Fecha: 2026-06-07
-- Objetivo: Habilitar procesamiento de confecciones (multi-proveedor)

-- ============================================================================
-- PASO 1: Crear tabla tipo_v2 (si no existe)
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.tipo_v2 (
  id_tipo SERIAL PRIMARY KEY,
  codigo_tipo TEXT UNIQUE NOT NULL,
  descp_tipo TEXT NOT NULL,
  proveedor_id INT,  -- 654 = Calzados, 638 = Confecciones
  activo BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_tipo_v2_proveedor ON public.tipo_v2(proveedor_id);
CREATE INDEX IF NOT EXISTS idx_tipo_v2_codigo ON public.tipo_v2(codigo_tipo);

-- Comentario
COMMENT ON TABLE public.tipo_v2 IS 'Tipos de producto (calzado, confecciones) para sistema multi-proveedor';

-- ============================================================================
-- PASO 2: Insertar tipos iniciales
-- ============================================================================

INSERT INTO public.tipo_v2 (id_tipo, codigo_tipo, descp_tipo, proveedor_id) VALUES
  (1, 'CALZADO', 'Calzado', 654),
  (2, 'CONFECCIONES', 'Confecciones', 638)
ON CONFLICT (codigo_tipo) DO NOTHING;

-- Asegurar que id_tipo=1 siempre sea CALZADO (para backward compatibility)
-- Si por alguna razón el ID cambió, corregir:
UPDATE public.tipo_v2 SET id_tipo = 1 WHERE codigo_tipo = 'CALZADO' AND id_tipo != 1;

-- ============================================================================
-- PASO 3: Agregar columna tipo_v2_id a registro_st_vt_rc_reposicion
-- ============================================================================

ALTER TABLE public.registro_st_vt_rc_reposicion
ADD COLUMN IF NOT EXISTS tipo_v2_id INT;

-- ============================================================================
-- PASO 4: Llenar TODOS los registros existentes con tipo_v2_id = 1 (CALZADO)
-- ============================================================================

-- Todos los datos históricos son calzados
UPDATE public.registro_st_vt_rc_reposicion
SET tipo_v2_id = 1
WHERE tipo_v2_id IS NULL;

-- ============================================================================
-- PASO 5: Agregar FK constraint a tipo_v2
-- ============================================================================

ALTER TABLE public.registro_st_vt_rc_reposicion
DROP CONSTRAINT IF EXISTS fk_registro_tipo_v2;

ALTER TABLE public.registro_st_vt_rc_reposicion
ADD CONSTRAINT fk_registro_tipo_v2
  FOREIGN KEY (tipo_v2_id)
  REFERENCES public.tipo_v2(id_tipo);

-- ============================================================================
-- PASO 6: Crear índice para performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_registro_tipo_v2
ON public.registro_st_vt_rc_reposicion(tipo_v2_id);

-- ============================================================================
-- PASO 7: Comentarios y documentación
-- ============================================================================

COMMENT ON COLUMN public.registro_st_vt_rc_reposicion.tipo_v2_id IS
'Tipo de producto: 1=CALZADO (proveedor 654), 2=CONFECCIONES (proveedor 638). Todos los datos históricos son calzados (1).';

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================

-- Verificar que todos los registros tienen tipo_v2_id = 1
DO $$
DECLARE
  v_count_null INT;
  v_count_total INT;
  v_count_calzado INT;
BEGIN
  SELECT COUNT(*) INTO v_count_null
  FROM public.registro_st_vt_rc_reposicion
  WHERE tipo_v2_id IS NULL;

  SELECT COUNT(*) INTO v_count_total
  FROM public.registro_st_vt_rc_reposicion;

  SELECT COUNT(*) INTO v_count_calzado
  FROM public.registro_st_vt_rc_reposicion
  WHERE tipo_v2_id = 1;

  RAISE NOTICE '============================================';
  RAISE NOTICE 'VERIFICACIÓN MIGRACIÓN 110:';
  RAISE NOTICE '============================================';
  RAISE NOTICE 'Total registros: %', v_count_total;
  RAISE NOTICE 'Registros con tipo_v2_id=1 (CALZADO): %', v_count_calzado;
  RAISE NOTICE 'Registros con tipo_v2_id NULL: %', v_count_null;

  IF v_count_null > 0 THEN
    RAISE WARNING 'HAY % REGISTROS SIN tipo_v2_id. Revisar.', v_count_null;
  ELSE
    RAISE NOTICE '✅ TODOS los registros tienen tipo_v2_id asignado';
  END IF;

  IF v_count_calzado = v_count_total THEN
    RAISE NOTICE '✅ TODOS los registros son CALZADO (tipo_v2_id=1)';
  END IF;

  RAISE NOTICE '============================================';
END $$;

-- ============================================================================
-- FIN MIGRACIÓN 110
-- ============================================================================
