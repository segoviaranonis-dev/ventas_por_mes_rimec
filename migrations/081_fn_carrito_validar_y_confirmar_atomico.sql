-- MIG-081 — Funciones server-side: VALIDAR + CONFIRMAR atómico (FOR UPDATE).
-- Reglas firmadas:
--   * No reserva stock (F=1).
--   * Validar emite token con ventana 60s (H).
--   * Confirmar exige token válido y re-chequea con bloqueo pesimista.

BEGIN;

-- ──────────────────────────────────────────────────────────────────────
-- carrito_validar(id_usuario)
-- Compara cantidades vs stock real y precio vs PPD.precio_lpn.
-- Emite token UUID; queda guardado en carrito_sesion para Confirmar.
-- ──────────────────────────────────────────────────────────────────────
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

  WITH detalle AS (
    SELECT
      ci.det_id,
      ci.cantidad_cajas        AS cajas_solicitadas,
      ci.precio_snapshot       AS precio_carrito,
      vs.cajas_disponibles     AS cajas_actuales,
      vs.lpn                   AS precio_actual,
      ppd.precio_lpn IS NOT NULL AS sigue_con_precio
    FROM public.carrito_item ci
    JOIN public.pedido_proveedor_detalle ppd ON ppd.id = ci.det_id
    LEFT JOIN public.v_stock_rimec vs ON vs.det_id = ci.det_id
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
  'MIG-081: valida cantidades y precios. Devuelve token UUID con ventana 60s para Confirmar.';

-- ──────────────────────────────────────────────────────────────────────
-- carrito_token_vigente(id_usuario, token)
-- Verifica que el token coincida y no haya vencido (60 s).
-- ──────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.carrito_token_vigente(
  p_id_usuario bigint,
  p_token uuid
)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.carrito_sesion
    WHERE id_usuario = p_id_usuario
      AND validacion_estado = 'OK'
      AND validacion_token  = p_token
      AND validada_en > now() - interval '60 seconds'
  );
$$;

COMMIT;

SELECT 'MIG-081 OK: carrito_validar + carrito_token_vigente' AS estado;
