-- ===========================================================================
-- MIG-094 — Fix ROBUSTO: Validar precios desde v_stock_rimec, no desde PPD
-- ===========================================================================
-- PROBLEMA:
--   La función carrito_validar() valida precio usando ppd.precio_lpn IS NOT NULL
--   pero los precios reales están en v_stock_rimec (con fallback automático).
--   Si ppd.precio_lpn es NULL pero v_stock_rimec.lpn existe, marca SIN_PRECIO incorrectamente.
--
-- SOLUCION ROBUSTA:
--   Cambiar la validación para que verifique si el precio_actual (de v_stock_rimec) existe.
--   Esto hace que RIMEC WEB sea un puro exhibidor: si la vista tiene precio, se vende.
--   No importa si hay intención de compra o no — la vista ya maneja el fallback.
-- ===========================================================================

BEGIN;

CREATE OR REPLACE FUNCTION public.carrito_validar(p_id_usuario bigint)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $function$
DECLARE
  v_sesion record;
  v_items jsonb := '[]'::jsonb;
  v_tiene_diferencias boolean := false;
  v_token uuid := gen_random_uuid();
  v_items_actualizados int := 0;
BEGIN
  SELECT * INTO v_sesion FROM public.carrito_sesion WHERE id_usuario = p_id_usuario;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('success', false, 'detail', 'SESION_INEXISTENTE');
  END IF;

  -- PASO 1: Recalcular precios de todos los items según configuración de factura
  WITH facturas_config AS (
    SELECT DISTINCT ON (pp_id, marca, caso)
      (f->>'pp_id')::bigint AS pp_id,
      f->>'marca' AS marca,
      f->>'caso' AS caso,
      COALESCE((f->>'lista_precio_id')::int, 1) AS lista_precio_id,
      ARRAY[
        COALESCE(NULLIF(f->'descuentos'->>0, '')::numeric, 0),
        COALESCE(NULLIF(f->'descuentos'->>1, '')::numeric, 0),
        COALESCE(NULLIF(f->'descuentos'->>2, '')::numeric, 0),
        COALESCE(NULLIF(f->'descuentos'->>3, '')::numeric, 0)
      ] AS descuentos
    FROM jsonb_array_elements(
      COALESCE(v_sesion.descuentos_lote->'facturas', '[]'::jsonb)
    ) AS f
    ORDER BY pp_id, marca, caso, (f->>'items_count')::int DESC
  ),
  items_con_precios AS (
    SELECT
      ci.det_id,
      ci.id_usuario,
      fc.lista_precio_id,
      -- Precio base según lista_precio_id de la factura
      CASE fc.lista_precio_id
        WHEN 1 THEN vs.lpn
        WHEN 2 THEN vs.lpc02
        WHEN 3 THEN vs.lpc03
        WHEN 4 THEN vs.lpc04
        ELSE vs.lpn
      END AS precio_base,
      fc.descuentos
    FROM public.carrito_item ci
    JOIN public.pedido_proveedor_detalle ppd ON ppd.id = ci.det_id
    LEFT JOIN public.v_stock_rimec vs ON vs.det_id = ci.det_id
    LEFT JOIN facturas_config fc ON fc.pp_id = ci.pp_id
      AND fc.marca = ci.marca_snapshot
      AND fc.caso = ci.caso_snapshot
    WHERE ci.id_usuario = p_id_usuario
  )
  -- Actualizar precio_snapshot aplicando descuentos en cascada
  UPDATE public.carrito_item ci
  SET precio_snapshot = (
    SELECT ROUND(
      COALESCE(icp.precio_base, 0) *
      (1 - COALESCE(icp.descuentos[1], 0) / 100.0) *
      (1 - COALESCE(icp.descuentos[2], 0) / 100.0) *
      (1 - COALESCE(icp.descuentos[3], 0) / 100.0) *
      (1 - COALESCE(icp.descuentos[4], 0) / 100.0)
    )::integer
    FROM items_con_precios icp
    WHERE icp.det_id = ci.det_id
  )
  WHERE ci.id_usuario = p_id_usuario
    AND ci.det_id IN (SELECT det_id FROM items_con_precios);

  GET DIAGNOSTICS v_items_actualizados = ROW_COUNT;

  -- Marcar todas las facturas como pre_autorizadas
  UPDATE public.carrito_sesion
  SET descuentos_lote = jsonb_set(
    descuentos_lote,
    '{facturas}',
    (
      SELECT jsonb_agg(
        jsonb_set(f, '{pre_autorizado}', 'true'::jsonb)
      )
      FROM jsonb_array_elements(descuentos_lote->'facturas') f
    ),
    true
  )
  WHERE id_usuario = p_id_usuario;

  -- PASO 2: Validar STOCK + PRECIO (desde v_stock_rimec)
  -- FIX MIG-094: Validar precio desde precio_actual (v_stock_rimec) en lugar de ppd.precio_lpn
  WITH facturas_config AS (
    SELECT DISTINCT ON (pp_id, marca, caso)
      (f->>'pp_id')::bigint AS pp_id,
      f->>'marca' AS marca,
      f->>'caso' AS caso,
      COALESCE((f->>'lista_precio_id')::int, 1) AS lista_precio_id
    FROM jsonb_array_elements(
      COALESCE(v_sesion.descuentos_lote->'facturas', '[]'::jsonb)
    ) AS f
    ORDER BY pp_id, marca, caso, (f->>'items_count')::int DESC
  ),
  detalle AS (
    SELECT
      ci.det_id,
      ci.cantidad_cajas        AS cajas_solicitadas,
      ci.precio_snapshot       AS precio_carrito,
      vs.cajas_disponibles     AS cajas_actuales,
      -- Precio actual desde v_stock_rimec (ya tiene fallback a evento cerrado más reciente)
      CASE fc.lista_precio_id
        WHEN 1 THEN vs.lpn
        WHEN 2 THEN vs.lpc02
        WHEN 3 THEN vs.lpc03
        WHEN 4 THEN vs.lpc04
        ELSE vs.lpn
      END AS precio_actual,
      -- FIX MIG-094: Validar precio desde v_stock_rimec, no desde ppd
      -- Si precio_actual IS NOT NULL, entonces hay precio disponible
      (CASE fc.lista_precio_id
        WHEN 1 THEN vs.lpn
        WHEN 2 THEN vs.lpc02
        WHEN 3 THEN vs.lpc03
        WHEN 4 THEN vs.lpc04
        ELSE vs.lpn
      END) IS NOT NULL AS sigue_con_precio
    FROM public.carrito_item ci
    JOIN public.pedido_proveedor_detalle ppd ON ppd.id = ci.det_id
    LEFT JOIN public.v_stock_rimec vs ON vs.det_id = ci.det_id
    LEFT JOIN facturas_config fc ON fc.pp_id = ci.pp_id
      AND fc.marca = ci.marca_snapshot
      AND fc.caso = ci.caso_snapshot
    WHERE ci.id_usuario = p_id_usuario
  )
  SELECT jsonb_agg(
    jsonb_build_object(
      'det_id', det_id,
      'cajas_solicitadas', cajas_solicitadas,
      'cajas_actuales', COALESCE(cajas_actuales, 0),
      'precio_carrito', precio_carrito,
      'precio_actual',  precio_actual,
      'ok', (
        COALESCE(cajas_actuales, 0) >= cajas_solicitadas
        AND sigue_con_precio
      ),
      'motivo', CASE
        WHEN NOT sigue_con_precio THEN 'SIN_PRECIO'
        WHEN COALESCE(cajas_actuales, 0) < cajas_solicitadas THEN 'STOCK_INSUFICIENTE'
        ELSE NULL
      END
    )
  ),
  bool_or(NOT (
    COALESCE(cajas_actuales, 0) >= cajas_solicitadas
    AND sigue_con_precio
  ))
  INTO v_items, v_tiene_diferencias
  FROM detalle;

  v_items := COALESCE(v_items, '[]'::jsonb);

  IF v_items = '[]'::jsonb THEN
    RETURN jsonb_build_object('success', false, 'detail', 'CARRITO_VACIO');
  END IF;

  -- PASO 3: Guardar estado de validación
  UPDATE public.carrito_sesion
  SET validada_en       = now(),
      validacion_token  = CASE WHEN v_tiene_diferencias THEN NULL ELSE v_token END,
      validacion_estado = CASE WHEN v_tiene_diferencias THEN 'DIFERENCIAS' ELSE 'OK' END
  WHERE id_usuario = p_id_usuario;

  RETURN jsonb_build_object(
    'success', true,
    'estado',  CASE WHEN v_tiene_diferencias THEN 'DIFERENCIAS' ELSE 'OK' END,
    'token',   CASE WHEN v_tiene_diferencias THEN NULL ELSE v_token END,
    'expira_en', CASE WHEN v_tiene_diferencias THEN NULL ELSE now() + interval '60 seconds' END,
    'items',  v_items,
    'items_recalculados', v_items_actualizados
  );
END;
$function$;

COMMENT ON FUNCTION public.carrito_validar(bigint) IS
  'MIG-094: validar precio desde v_stock_rimec (con fallback automático) — RIMEC WEB es exhibidor puro';

COMMIT;

SELECT 'MIG-094 OK: carrito_validar usa precios de v_stock_rimec (robusta)' AS estado;
