-- MIG-092 — Funciones RPC para aprobación/rechazo de pedidos web
-- Permite a admins aprobar o rechazar pedidos desde el panel de aprobaciones

BEGIN;

-- ══════════════════════════════════════════════════════════════════════════════
-- Verificar columnas necesarias en pedido_venta_rimec
-- ══════════════════════════════════════════════════════════════════════════════
DO $$
BEGIN
  -- fecha_aprobacion
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'pedido_venta_rimec'
      AND column_name = 'fecha_aprobacion'
  ) THEN
    ALTER TABLE pedido_venta_rimec ADD COLUMN fecha_aprobacion timestamp;
  END IF;

  -- aprobado_por_id
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'pedido_venta_rimec'
      AND column_name = 'aprobado_por_id'
  ) THEN
    ALTER TABLE pedido_venta_rimec ADD COLUMN aprobado_por_id bigint REFERENCES usuario_v2(id_usuario);
  END IF;

  -- fecha_rechazo
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'pedido_venta_rimec'
      AND column_name = 'fecha_rechazo'
  ) THEN
    ALTER TABLE pedido_venta_rimec ADD COLUMN fecha_rechazo timestamp;
  END IF;

  -- rechazado_por_id
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'pedido_venta_rimec'
      AND column_name = 'rechazado_por_id'
  ) THEN
    ALTER TABLE pedido_venta_rimec ADD COLUMN rechazado_por_id bigint REFERENCES usuario_v2(id_usuario);
  END IF;

  -- motivo_rechazo
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'pedido_venta_rimec'
      AND column_name = 'motivo_rechazo'
  ) THEN
    ALTER TABLE pedido_venta_rimec ADD COLUMN motivo_rechazo text;
  END IF;
END $$;


-- ══════════════════════════════════════════════════════════════════════════════
-- FUNCIÓN: aprobar_pedido
-- ══════════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.aprobar_pedido(
  p_pedido_id bigint,
  p_admin_id bigint
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $function$
DECLARE
  v_pedido RECORD;
BEGIN
  -- 1. Validar admin
  IF NOT public.fn_es_usuario_vendedor_o_admin(p_admin_id) THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('Usuario %s no tiene permisos de admin', p_admin_id)
    );
  END IF;

  -- 2. Verificar que el pedido existe
  SELECT * INTO v_pedido
  FROM pedido_venta_rimec
  WHERE id = p_pedido_id;

  IF NOT FOUND THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('Pedido %s no encontrado', p_pedido_id)
    );
  END IF;

  -- 3. Verificar que está pendiente
  IF v_pedido.estado NOT IN ('PENDIENTE', 'pendiente', NULL) THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('Pedido %s ya fue procesado (estado: %s)', p_pedido_id, v_pedido.estado)
    );
  END IF;

  -- 4. Actualizar estado a APROBADO
  UPDATE pedido_venta_rimec
  SET
    estado = 'APROBADO',
    fecha_aprobacion = NOW(),
    aprobado_por_id = p_admin_id
  WHERE id = p_pedido_id;

  RETURN jsonb_build_object(
    'success', true,
    'pedido_id', p_pedido_id,
    'estado', 'APROBADO'
  );
END;
$function$;


-- ══════════════════════════════════════════════════════════════════════════════
-- FUNCIÓN: rechazar_pedido
-- ══════════════════════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.rechazar_pedido(
  p_pedido_id bigint,
  p_admin_id bigint,
  p_motivo text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $function$
DECLARE
  v_pedido RECORD;
BEGIN
  -- 1. Validar admin
  IF NOT public.fn_es_usuario_vendedor_o_admin(p_admin_id) THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('Usuario %s no tiene permisos de admin', p_admin_id)
    );
  END IF;

  -- 2. Verificar que el pedido existe
  SELECT * INTO v_pedido
  FROM pedido_venta_rimec
  WHERE id = p_pedido_id;

  IF NOT FOUND THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('Pedido %s no encontrado', p_pedido_id)
    );
  END IF;

  -- 3. Verificar que está pendiente
  IF v_pedido.estado NOT IN ('PENDIENTE', 'pendiente', NULL) THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('Pedido %s ya fue procesado (estado: %s)', p_pedido_id, v_pedido.estado)
    );
  END IF;

  -- 4. Actualizar estado a RECHAZADO
  UPDATE pedido_venta_rimec
  SET
    estado = 'RECHAZADO',
    fecha_rechazo = NOW(),
    rechazado_por_id = p_admin_id,
    motivo_rechazo = p_motivo
  WHERE id = p_pedido_id;

  RETURN jsonb_build_object(
    'success', true,
    'pedido_id', p_pedido_id,
    'estado', 'RECHAZADO',
    'motivo', p_motivo
  );
END;
$function$;

COMMIT;

-- ══════════════════════════════════════════════════════════════════════════════
-- Comentarios
-- ══════════════════════════════════════════════════════════════════════════════
COMMENT ON FUNCTION public.aprobar_pedido IS
  'Aprueba un pedido web. Solo usuarios admin/vendedor. Cambia estado a APROBADO.';

COMMENT ON FUNCTION public.rechazar_pedido IS
  'Rechaza un pedido web. Solo usuarios admin/vendedor. Cambia estado a RECHAZADO.';
