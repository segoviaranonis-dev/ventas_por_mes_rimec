-- MIG-084 — Fix carrito_validar: validar precio según lista_precio_id de cada factura
-- Problema: MIG-081 compara siempre contra vs.lpn, pero MIG-083 permite lista_precio_id diferente por factura.
-- Solución: extraer lista_precio_id de descuentos_lote.facturas y comparar contra columna correcta.

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
BEGIN
  SELECT * INTO v_sesion FROM public.carrito_sesion WHERE id_usuario = p_id_usuario;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('success', false, 'detail', 'SESION_INEXISTENTE');
  END IF;

  -- Para cada item, determinar la lista_precio_id de su factura (pp_id + marca + caso)
  -- y comparar contra la columna correcta de v_stock_rimec
  WITH facturas_config AS (
    SELECT
      (f->>'pp_id')::bigint AS pp_id,
      f->>'marca' AS marca,
      f->>'caso' AS caso,
      COALESCE((f->>'lista_precio_id')::int, 1) AS lista_precio_id
    FROM jsonb_array_elements(
      COALESCE(v_sesion.descuentos_lote->'facturas', '[]'::jsonb)
    ) AS f
  ),
  detalle AS (
    SELECT
      ci.det_id,
      ci.cantidad_cajas        AS cajas_solicitadas,
      ci.precio_snapshot       AS precio_carrito,
      vs.cajas_disponibles     AS cajas_actuales,
      -- Seleccionar columna de precio según lista_precio_id de la factura
      CASE fc.lista_precio_id
        WHEN 1 THEN vs.lpn
        WHEN 2 THEN vs.lpc02
        WHEN 3 THEN vs.lpc03
        WHEN 4 THEN vs.lpc04
        ELSE vs.lpn
      END AS precio_actual,
      ppd.precio_lpn IS NOT NULL AS sigue_con_precio
    FROM public.carrito_item ci
    JOIN public.pedido_proveedor_detalle ppd ON ppd.id = ci.det_id
    LEFT JOIN public.v_stock_rimec vs ON vs.det_id = ci.det_id
    -- JOIN con facturas_config para obtener lista_precio_id
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
        AND precio_actual IS NOT DISTINCT FROM precio_carrito
      ),
      'motivo', CASE
        WHEN NOT sigue_con_precio THEN 'SIN_PRECIO'
        WHEN COALESCE(cajas_actuales, 0) < cajas_solicitadas THEN 'STOCK_INSUFICIENTE'
        WHEN precio_actual IS DISTINCT FROM precio_carrito THEN 'PRECIO_CAMBIO'
        ELSE NULL
      END
    )
  ),
  bool_or(NOT (
    COALESCE(cajas_actuales, 0) >= cajas_solicitadas
    AND sigue_con_precio
    AND precio_actual IS NOT DISTINCT FROM precio_carrito
  ))
  INTO v_items, v_tiene_diferencias
  FROM detalle;

  v_items := COALESCE(v_items, '[]'::jsonb);

  IF v_items = '[]'::jsonb THEN
    RETURN jsonb_build_object('success', false, 'detail', 'CARRITO_VACIO');
  END IF;

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
    'items',  v_items
  );
END;
$function$;

COMMENT ON FUNCTION public.carrito_validar(bigint) IS
  'MIG-084: valida cantidades y precios según lista_precio_id de cada factura (MIG-083).';

COMMIT;

SELECT 'MIG-084 OK: carrito_validar multi-lista' AS estado;
