-- =============================================================================
-- MIGRACIÓN: 063_pp_sello_auditable.sql
-- OBJETIVO: Fortalecer Pasar a Compra con sello auditable incremental
-- FECHA: 2026-05-31
-- OT: OT-NEXUS-PP-SELLO-AUDITABLE-003
--
-- CAMBIOS:
--   1. Agregar campos de auditoría temporal a pedido_proveedor
--   2. Agregar snapshot de categoría/tipo/precio a compra_legal
--   3. Agregar snapshot en vínculo compra_legal_pedido
--   4. Crear tabla de log de cambios de estado
--   5. Agregar UNIQUE constraint para prevenir duplicados
--
-- SEGURIDAD:
--   - Todas las columnas son NULLABLE (no obliga datos existentes)
--   - IF NOT EXISTS (idempotente)
--   - UNIQUE solo si no hay duplicados previos
--   - No modifica datos existentes
--   - No cambia estados
--
-- ROLLBACK: No destructivo - columnas pueden dejarse si no interfieren
-- =============================================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. PEDIDO_PROVEEDOR: Auditoría temporal y de usuario
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE pedido_proveedor
ADD COLUMN IF NOT EXISTS enviado_at timestamptz,
ADD COLUMN IF NOT EXISTS enviado_por bigint REFERENCES usuario_v2(id_usuario),
ADD COLUMN IF NOT EXISTS cerrado_at timestamptz,
ADD COLUMN IF NOT EXISTS cerrado_por bigint REFERENCES usuario_v2(id_usuario);

COMMENT ON COLUMN pedido_proveedor.enviado_at IS 'Timestamp cuando PP pasó a Compra Legal (estado=ENVIADO)';
COMMENT ON COLUMN pedido_proveedor.enviado_por IS 'Usuario que ejecutó "Pasar a Compra"';
COMMENT ON COLUMN pedido_proveedor.cerrado_at IS 'Timestamp cuando PP se cerró definitivamente';
COMMENT ON COLUMN pedido_proveedor.cerrado_por IS 'Usuario que cerró el PP';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. COMPRA_LEGAL: Snapshot de categoría comercial y pricing
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE compra_legal
ADD COLUMN IF NOT EXISTS categoria_id bigint REFERENCES categoria_v2(id_categoria),
ADD COLUMN IF NOT EXISTS tipo_v2_id bigint REFERENCES tipo_v2(id_tipo),
ADD COLUMN IF NOT EXISTS precio_evento_id bigint REFERENCES precio_evento(id);

COMMENT ON COLUMN compra_legal.categoria_id IS 'Categoría comercial predominante de esta compra (ej: COMPRA PREVIA=2)';
COMMENT ON COLUMN compra_legal.tipo_v2_id IS 'Tipo predominante (CALZADOS=1, CONFECCIONES=2)';
COMMENT ON COLUMN compra_legal.precio_evento_id IS 'Evento de precio predominante usado en los PPs de esta compra';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. COMPRA_LEGAL_PEDIDO: Snapshot del vínculo PP → CL
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE compra_legal_pedido
ADD COLUMN IF NOT EXISTS categoria_id bigint REFERENCES categoria_v2(id_categoria),
ADD COLUMN IF NOT EXISTS precio_evento_id bigint REFERENCES precio_evento(id),
ADD COLUMN IF NOT EXISTS pares_snapshot integer,
ADD COLUMN IF NOT EXISTS snapshot_at timestamptz DEFAULT now();

COMMENT ON COLUMN compra_legal_pedido.categoria_id IS 'Categoría del PP al momento de pasar a compra (snapshot)';
COMMENT ON COLUMN compra_legal_pedido.precio_evento_id IS 'Evento de precio del PP al momento de pasar a compra (snapshot)';
COMMENT ON COLUMN compra_legal_pedido.pares_snapshot IS 'Pares comprometidos del PP al momento de pasar a compra (snapshot)';
COMMENT ON COLUMN compra_legal_pedido.snapshot_at IS 'Timestamp del snapshot';

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. PEDIDO_PROVEEDOR_LOG: Tabla de auditoría de cambios de estado
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pedido_proveedor_log (
  id bigserial PRIMARY KEY,
  pp_id bigint NOT NULL REFERENCES pedido_proveedor(id) ON DELETE CASCADE,
  estado_anterior text,
  estado_nuevo text NOT NULL,
  timestamp timestamptz DEFAULT now() NOT NULL,
  usuario_id bigint REFERENCES usuario_v2(id_usuario),
  compra_legal_id bigint REFERENCES compra_legal(id),
  observaciones text
);

CREATE INDEX IF NOT EXISTS idx_pp_log_pp_id ON pedido_proveedor_log(pp_id);
CREATE INDEX IF NOT EXISTS idx_pp_log_timestamp ON pedido_proveedor_log(timestamp DESC);

COMMENT ON TABLE pedido_proveedor_log IS 'Log de auditoría de cambios de estado de Pedidos Proveedor';
COMMENT ON COLUMN pedido_proveedor_log.pp_id IS 'ID del Pedido Proveedor';
COMMENT ON COLUMN pedido_proveedor_log.estado_anterior IS 'Estado previo (NULL si es creación)';
COMMENT ON COLUMN pedido_proveedor_log.estado_nuevo IS 'Estado nuevo';
COMMENT ON COLUMN pedido_proveedor_log.timestamp IS 'Momento del cambio';
COMMENT ON COLUMN pedido_proveedor_log.usuario_id IS 'Usuario que ejecutó el cambio';
COMMENT ON COLUMN pedido_proveedor_log.compra_legal_id IS 'Compra Legal relacionada (si aplica)';
COMMENT ON COLUMN pedido_proveedor_log.observaciones IS 'Notas adicionales del cambio';

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. UNIQUE CONSTRAINT: Prevenir duplicados PP en misma CL
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
  -- Solo agregar si no existe (idempotente)
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_compra_legal_pedido_pp'
      AND conrelid = 'compra_legal_pedido'::regclass
  ) THEN
    ALTER TABLE compra_legal_pedido
    ADD CONSTRAINT uq_compra_legal_pedido_pp
    UNIQUE (compra_legal_id, pedido_proveedor_id);

    RAISE NOTICE 'UNIQUE constraint uq_compra_legal_pedido_pp agregado exitosamente';
  ELSE
    RAISE NOTICE 'UNIQUE constraint uq_compra_legal_pedido_pp ya existe - skip';
  END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. VERIFICACIÓN FINAL
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
  v_pp_cols integer;
  v_cl_cols integer;
  v_clp_cols integer;
  v_log_exists boolean;
BEGIN
  -- Contar columnas agregadas
  SELECT COUNT(*) INTO v_pp_cols
  FROM information_schema.columns
  WHERE table_name = 'pedido_proveedor'
    AND column_name IN ('enviado_at', 'enviado_por', 'cerrado_at', 'cerrado_por');

  SELECT COUNT(*) INTO v_cl_cols
  FROM information_schema.columns
  WHERE table_name = 'compra_legal'
    AND column_name IN ('categoria_id', 'tipo_v2_id', 'precio_evento_id');

  SELECT COUNT(*) INTO v_clp_cols
  FROM information_schema.columns
  WHERE table_name = 'compra_legal_pedido'
    AND column_name IN ('categoria_id', 'precio_evento_id', 'pares_snapshot', 'snapshot_at');

  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'pedido_proveedor_log'
  ) INTO v_log_exists;

  -- Reportar
  RAISE NOTICE '=== MIGRACIÓN 063 COMPLETADA ===';
  RAISE NOTICE 'pedido_proveedor: % columnas de auditoría', v_pp_cols;
  RAISE NOTICE 'compra_legal: % columnas de snapshot', v_cl_cols;
  RAISE NOTICE 'compra_legal_pedido: % columnas de snapshot', v_clp_cols;
  RAISE NOTICE 'pedido_proveedor_log: %', CASE WHEN v_log_exists THEN 'EXISTE' ELSE 'NO EXISTE' END;

  IF v_pp_cols = 4 AND v_cl_cols = 3 AND v_clp_cols = 4 AND v_log_exists THEN
    RAISE NOTICE '[OK] Migración 063 aplicada completamente';
  ELSE
    RAISE WARNING '[PARCIAL] Migración 063 incompleta - revisar';
  END IF;
END $$;

COMMIT;

-- =============================================================================
-- FIN MIGRACIÓN 063
-- =============================================================================
