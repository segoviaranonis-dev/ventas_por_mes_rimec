-- MIG-082 — confirmar_pedido_web: token de validación + FOR UPDATE pesimista.
-- Reglas firmadas (H=obligatorio, F=no reserva, G=gana primero):
--   * Exige token de carrito_validar emitido en últimos 60 s.
--   * Bloquea PPDs con FOR UPDATE (orden estable, sin deadlocks).
--   * Re-verifica stock y precio dentro de la transacción.
--   * Vacía carrito_sesion + carrito_item al confirmar OK.

BEGIN;

-- Drop existing MIG-072 version (11 params) to avoid ambiguous function error
DROP FUNCTION IF EXISTS public.confirmar_pedido_web(
  bigint, bigint, bigint, integer, numeric, numeric, numeric, numeric, integer, numeric, jsonb
);

CREATE OR REPLACE FUNCTION public.confirmar_pedido_web(
  p_cliente_id      bigint,
  p_vendedor_id     bigint  DEFAULT NULL,
  p_plazo_id        bigint  DEFAULT NULL,
  p_lista_precio_id integer DEFAULT 1,
  p_descuento_1     numeric DEFAULT 0,
  p_descuento_2     numeric DEFAULT 0,
  p_descuento_3     numeric DEFAULT 0,
  p_descuento_4     numeric DEFAULT 0,
  p_total_pares     integer DEFAULT 0,
  p_total_monto     numeric DEFAULT 0,
  p_payload         jsonb   DEFAULT '{}'::jsonb,
  p_validacion_token uuid   DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $function$
DECLARE
  v_nro_pedido    TEXT;
  v_pedido_id     BIGINT;
  v_lote          JSONB;
  v_factura       JSONB;
  v_item          JSONB;
  v_pp_id         BIGINT;
  v_pp_nro        TEXT;
  v_marca_txt     TEXT;
  v_marca_id      BIGINT;
  v_caso_txt      TEXT;
  v_caso_id       BIGINT;
  v_fi_id         BIGINT;
  v_nro_fi        TEXT;
  v_fi_pares      INTEGER;
  v_fi_monto      NUMERIC;
  v_det_id        BIGINT;
  v_pares         INTEGER;
  v_cajas         INTEGER;
  v_facturas_out  JSONB := '[]'::JSONB;
  v_total_fi      INTEGER := 0;
  v_db_cantidad_pares INTEGER;
  v_db_pares_vendidos INTEGER;
  v_payload_det_ids bigint[];
  v_precio_actual numeric;
  v_precio_payload numeric;
BEGIN
  -- ── 0. Identidad ─────────────────────────────────────────────────────────
  IF p_vendedor_id IS NULL THEN
    RETURN jsonb_build_object('success', false, 'error', 'p_vendedor_id obligatorio.', 'detail', 'VENDEDOR_FALTANTE');
  END IF;
  IF p_cliente_id IS NULL THEN
    RETURN jsonb_build_object('success', false, 'error', 'p_cliente_id obligatorio.', 'detail', 'CLIENTE_FALTANTE');
  END IF;

  PERFORM 1 FROM public.usuario_v2 u
  WHERE u.id_usuario = p_vendedor_id
    AND public.fn_es_usuario_vendedor_o_admin(u.id_usuario);
  IF NOT FOUND THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('Usuario %s no existe o no tiene rol VENDEDOR/ADMIN.', p_vendedor_id),
      'detail', 'VENDEDOR_INVALIDO'
    );
  END IF;

  -- ── 0.1. Token de validación (MIG-082) ───────────────────────────────────
  IF p_validacion_token IS NULL THEN
    RETURN jsonb_build_object('success', false, 'error', 'Falta token de validación.', 'detail', 'VALIDACION_REQUERIDA');
  END IF;

  IF NOT public.carrito_token_vigente(p_vendedor_id, p_validacion_token) THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', 'Token de validación vencido o inválido. Presioná VALIDAR de nuevo.',
      'detail', 'VALIDACION_VENCIDA'
    );
  END IF;

  -- ── 1. Payload ──────────────────────────────────────────────────────────
  IF p_payload IS NULL OR jsonb_typeof(p_payload->'lotes') <> 'array' THEN
    RETURN jsonb_build_object('success', false, 'error', 'Payload inválido: falta lotes[]');
  END IF;
  IF jsonb_array_length(p_payload->'lotes') = 0 THEN
    RETURN jsonb_build_object('success', false, 'error', 'Carrito vacío');
  END IF;

  -- ── 1.1. Lock pesimista sobre todos los PPDs del payload (orden estable) ─
  SELECT array_agg(DISTINCT (it->>'det_id')::bigint ORDER BY (it->>'det_id')::bigint)
  INTO v_payload_det_ids
  FROM jsonb_array_elements(p_payload->'lotes') lt,
       jsonb_array_elements(lt->'facturas') fa,
       jsonb_array_elements(fa->'items') it
  WHERE (it->>'det_id') IS NOT NULL;

  IF v_payload_det_ids IS NOT NULL AND array_length(v_payload_det_ids, 1) > 0 THEN
    PERFORM 1
    FROM public.pedido_proveedor_detalle
    WHERE id = ANY(v_payload_det_ids)
    ORDER BY id
    FOR UPDATE;
  END IF;

  -- ── 2. Número pedido ────────────────────────────────────────────────────
  v_nro_pedido := 'PVR-' || EXTRACT(YEAR FROM NOW())::TEXT || '-' ||
                  LPAD(FLOOR(RANDOM() * 1000000)::TEXT, 6, '0');

  -- ── 3. Cabecera ─────────────────────────────────────────────────────────
  INSERT INTO public.pedido_venta_rimec (
    nro_pedido, cliente_id, vendedor_id, plazo_id, lista_precio_id,
    descuento_1, descuento_2, descuento_3, descuento_4,
    total_pares, total_monto, estado, payload_json
  ) VALUES (
    v_nro_pedido, p_cliente_id, p_vendedor_id, p_plazo_id, p_lista_precio_id,
    p_descuento_1, p_descuento_2, p_descuento_3, p_descuento_4,
    p_total_pares, p_total_monto, 'PENDIENTE', p_payload
  )
  RETURNING id INTO v_pedido_id;

  -- ── 4. Lotes / facturas / items ─────────────────────────────────────────
  FOR v_lote IN SELECT * FROM jsonb_array_elements(p_payload->'lotes') LOOP
    v_pp_id  := (v_lote->>'pp_id')::BIGINT;
    v_pp_nro := COALESCE(v_lote->>'pp_nro', v_pp_id::TEXT);

    IF jsonb_typeof(v_lote->'facturas') <> 'array'
       OR jsonb_array_length(v_lote->'facturas') = 0 THEN
      RAISE EXCEPTION 'Lote PP=% sin facturas[]', v_pp_id;
    END IF;

    FOR v_factura IN SELECT * FROM jsonb_array_elements(v_lote->'facturas') LOOP
      v_marca_txt := NULLIF(TRIM(COALESCE(v_factura->>'marca', '')), '');
      v_marca_id  := NULLIF(v_factura->>'marca_id', '')::BIGINT;
      v_caso_txt  := NULLIF(TRIM(COALESCE(v_factura->>'caso', '')), '');

      IF v_caso_txt IS NOT NULL THEN
        SELECT id INTO v_caso_id
        FROM public.caso_precio_biblioteca
        WHERE nombre_caso = v_caso_txt
        LIMIT 1;
      ELSE
        v_caso_id := NULLIF(v_factura->>'caso_id', '')::BIGINT;
      END IF;

      v_fi_pares := COALESCE((v_factura->>'total_pares')::INTEGER, 0);
      v_fi_monto := COALESCE((v_factura->>'total_monto')::NUMERIC, 0);

      IF jsonb_typeof(v_factura->'items') <> 'array'
         OR jsonb_array_length(v_factura->'items') = 0 THEN
        RAISE EXCEPTION 'Factura PP=%, marca=%, caso=% sin items[]',
          v_pp_id, COALESCE(v_marca_txt, '∅'), COALESCE(v_caso_txt, '∅');
      END IF;

      v_nro_fi := generar_nro_factura_interna(v_pp_id);

      INSERT INTO public.factura_interna (
        nro_factura, pp_id, pedido_id,
        cliente_id, vendedor_id, plazo_id, lista_precio_id,
        descuento_1, descuento_2, descuento_3, descuento_4,
        total_pares, total_monto, estado,
        marca, marca_id, caso, caso_id
      ) VALUES (
        v_nro_fi, v_pp_id, v_pedido_id,
        p_cliente_id, p_vendedor_id, p_plazo_id, p_lista_precio_id,
        p_descuento_1, p_descuento_2, p_descuento_3, p_descuento_4,
        v_fi_pares, v_fi_monto, 'RESERVADA',
        v_marca_txt, v_marca_id, v_caso_txt, v_caso_id
      )
      RETURNING id INTO v_fi_id;

      FOR v_item IN SELECT * FROM jsonb_array_elements(v_factura->'items') LOOP
        v_det_id := NULLIF(v_item->>'det_id', '')::BIGINT;
        v_pares  := COALESCE((v_item->>'pares')::INTEGER, 0);
        v_cajas  := COALESCE((v_item->>'cajas')::INTEGER, 0);
        v_precio_payload := COALESCE((v_item->>'precio_base')::NUMERIC, NULL);

        IF v_det_id IS NOT NULL THEN
          SELECT precio_lpn INTO v_precio_actual
          FROM public.pedido_proveedor_detalle
          WHERE id = v_det_id;

          IF v_precio_actual IS NULL THEN
            RAISE EXCEPTION 'PPD % perdió snapshot de precio entre VALIDAR y CONFIRMAR.', v_det_id;
          END IF;

          IF v_precio_payload IS NOT NULL
             AND v_precio_actual IS DISTINCT FROM v_precio_payload THEN
            RAISE EXCEPTION 'Precio cambió para PPD %: payload %, actual %.',
              v_det_id, v_precio_payload, v_precio_actual;
          END IF;
        END IF;

        INSERT INTO public.factura_interna_detalle (
          factura_id, ppd_id, cajas, pares,
          precio_unit, precio_lista, precio_neto, subtotal,
          linea_snapshot
        ) VALUES (
          v_fi_id, v_det_id, v_cajas, v_pares,
          COALESCE((v_item->>'precio_neto')::NUMERIC, 0),
          COALESCE((v_item->>'precio_base')::NUMERIC, 0),
          COALESCE((v_item->>'precio_neto')::NUMERIC, 0),
          COALESCE((v_item->>'subtotal')::NUMERIC, 0),
          jsonb_build_object(
            'linea_codigo', v_item->>'linea_codigo',
            'ref_codigo',   v_item->>'ref_codigo',
            'color_nombre', v_item->>'color_nombre',
            'gradas_fmt',   v_item->>'gradas_fmt',
            'imagen_url',   v_item->>'imagen_url',
            'marca',        v_marca_txt,
            'caso',         v_caso_txt
          )
        );

        IF v_det_id IS NOT NULL AND v_pares > 0 THEN
          SELECT cantidad_pares, COALESCE(pares_vendidos, 0)
          INTO v_db_cantidad_pares, v_db_pares_vendidos
          FROM public.pedido_proveedor_detalle
          WHERE id = v_det_id;

          IF (v_db_pares_vendidos + v_pares) > v_db_cantidad_pares THEN
            RAISE EXCEPTION 'Stock insuficiente L% R% (PP: %). Solicitado: %, Disponible: %.',
              v_item->>'linea_codigo', v_item->>'ref_codigo', v_pp_nro,
              v_pares, (v_db_cantidad_pares - v_db_pares_vendidos);
          END IF;

          UPDATE public.pedido_proveedor_detalle
          SET pares_vendidos = COALESCE(pares_vendidos, 0) + v_pares
          WHERE id = v_det_id;
        END IF;
      END LOOP;

      v_facturas_out := v_facturas_out || jsonb_build_object(
        'fi_id', v_fi_id, 'nro_factura', v_nro_fi, 'pp_id', v_pp_id, 'pp_nro', v_pp_nro,
        'marca', v_marca_txt, 'marca_id', v_marca_id, 'caso', v_caso_txt, 'caso_id', v_caso_id,
        'total_pares', v_fi_pares, 'total_monto', v_fi_monto
      );
      v_total_fi := v_total_fi + 1;
    END LOOP;
  END LOOP;

  -- ── 7. Vaciar carrito persistente (MIG-080) ──────────────────────────────
  DELETE FROM public.carrito_item   WHERE id_usuario = p_vendedor_id;
  DELETE FROM public.carrito_sesion WHERE id_usuario = p_vendedor_id;

  RETURN jsonb_build_object(
    'success',        true,
    'pedido_id',      v_pedido_id,
    'nro_pedido',     v_nro_pedido,
    'total_facturas', v_total_fi,
    'facturas',       v_facturas_out
  );

EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object(
    'success', false,
    'error',   SQLERRM,
    'detail',  SQLSTATE
  );
END;
$function$;

COMMENT ON FUNCTION public.confirmar_pedido_web IS
  'MIG-082: agrega token de validación obligatorio + FOR UPDATE pesimista + revalidación precio + limpieza carrito.';

COMMIT;

SELECT 'MIG-082 OK: confirmar_pedido_web con token y lock' AS estado;
