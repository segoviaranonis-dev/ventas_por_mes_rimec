-- MIG-155 — confirmar_pedido_web: excepción PROMOCIONAL LPC03=LPN (paridad getPrecioActivo)
-- Hotfix 2026-07-15 · det 469 lista 3 payload 126070 vs BD lpc03 196600

BEGIN;

CREATE OR REPLACE FUNCTION public.fn_precio_tier_vista(
  p_lista integer,
  p_lpn numeric,
  p_lpc02 numeric,
  p_lpc03 numeric,
  p_lpc04 numeric,
  p_descp_caso text
)
RETURNS numeric
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE p_lista
    WHEN 1 THEN p_lpn
    WHEN 2 THEN p_lpc02
    WHEN 3 THEN
      CASE
        WHEN UPPER(TRIM(COALESCE(p_descp_caso, ''))) = 'PROMOCIONAL' THEN p_lpn
        ELSE p_lpc03
      END
    WHEN 4 THEN p_lpc04
    ELSE p_lpn
  END;
$$;

COMMENT ON FUNCTION public.fn_precio_tier_vista(integer, numeric, numeric, numeric, numeric, text) IS
  'Tier activo vista stock — PROMOCIONAL lista 3 = LPN (RIMEC Web).';

DROP FUNCTION IF EXISTS public.confirmar_pedido_web(
  bigint, bigint, bigint, integer, numeric, numeric, numeric, numeric, integer, numeric, jsonb, uuid
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
  v_sesion        RECORD;
  v_lote          JSONB;
  v_factura       JSONB;
  v_item          JSONB;
  v_pp_id         BIGINT;
  v_pp_id_fi      BIGINT;
  v_pp_nro        TEXT;
  v_is_pe_lote    BOOLEAN;
  v_is_pe_item    BOOLEAN;
  v_is_pe_ppd     BOOLEAN;
  v_is_pe_staging BOOLEAN;
  v_pe_stock_id   BIGINT;
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
  v_precio_bd_lista numeric;
  v_precio_payload numeric;
  v_lista_factura integer;
  c_pe_det_base   CONSTANT bigint := 800000000;
BEGIN
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

  SELECT * INTO v_sesion FROM public.carrito_sesion WHERE id_usuario = p_vendedor_id;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('success', false, 'error', 'Sesión no encontrada', 'detail', 'SESION_INEXISTENTE');
  END IF;

  IF p_payload IS NULL OR jsonb_typeof(p_payload->'lotes') <> 'array' THEN
    RETURN jsonb_build_object('success', false, 'error', 'Payload inválido: falta lotes[]');
  END IF;
  IF jsonb_array_length(p_payload->'lotes') = 0 THEN
    RETURN jsonb_build_object('success', false, 'error', 'Carrito vacío');
  END IF;

  SELECT array_agg(DISTINCT (it->>'det_id')::bigint ORDER BY (it->>'det_id')::bigint)
  INTO v_payload_det_ids
  FROM jsonb_array_elements(p_payload->'lotes') lt,
       jsonb_array_elements(lt->'facturas') fa,
       jsonb_array_elements(fa->'items') it
  WHERE (it->>'det_id') IS NOT NULL
    AND (it->>'det_id')::bigint < c_pe_det_base;

  IF v_payload_det_ids IS NOT NULL AND array_length(v_payload_det_ids, 1) > 0 THEN
    PERFORM 1
    FROM public.pedido_proveedor_detalle
    WHERE id = ANY(v_payload_det_ids)
    ORDER BY id
    FOR UPDATE;
  END IF;

  v_nro_pedido := 'PVR-' || EXTRACT(YEAR FROM NOW())::TEXT || '-' ||
                  LPAD(FLOOR(RANDOM() * 1000000)::TEXT, 6, '0');

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

  FOR v_lote IN SELECT * FROM jsonb_array_elements(p_payload->'lotes') LOOP
    v_pp_id := NULLIF(v_lote->>'pp_id', '')::BIGINT;
    v_pp_nro := COALESCE(v_lote->>'pp_nro', v_pp_id::TEXT, 'PE');

    v_is_pe_lote := COALESCE((v_lote->>'origen_pe')::boolean, false)
                    OR (v_pp_id IS NOT NULL AND v_pp_id < 0);
    v_pp_id_fi := CASE WHEN v_is_pe_lote THEN NULL ELSE v_pp_id END;

    IF NOT v_is_pe_lote THEN
      IF v_pp_id IS NULL OR NOT EXISTS (SELECT 1 FROM public.pedido_proveedor WHERE id = v_pp_id) THEN
        RETURN jsonb_build_object(
          'success', false,
          'error', format('PP %s no existe. Vacá el carrito y volvé a cargar desde catálogo.', COALESCE(v_pp_id::text, '?')),
          'detail', 'PP_INVALIDO'
        );
      END IF;
    END IF;

    IF jsonb_typeof(v_lote->'facturas') <> 'array'
       OR jsonb_array_length(v_lote->'facturas') = 0 THEN
      RAISE EXCEPTION 'Lote PP=% sin facturas[]', COALESCE(v_pp_id::text, 'PE');
    END IF;

    FOR v_factura IN SELECT * FROM jsonb_array_elements(v_lote->'facturas') LOOP
      v_marca_txt := NULLIF(TRIM(COALESCE(v_factura->>'marca', '')), '');
      v_marca_id  := NULLIF(v_factura->>'marca_id', '')::BIGINT;

      IF v_marca_id IS NOT NULL AND v_marca_id <= 0 THEN
        v_marca_id := NULL;
      END IF;
      IF v_marca_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.marca_v2 mv WHERE mv.id_marca = v_marca_id
      ) THEN
        v_marca_id := NULL;
      END IF;
      IF v_marca_id IS NULL AND v_marca_txt IS NOT NULL THEN
        SELECT mv.id_marca INTO v_marca_id
        FROM public.marca_v2 mv
        WHERE UPPER(TRIM(mv.descp_marca)) = UPPER(v_marca_txt)
        LIMIT 1;
      END IF;

      v_caso_txt  := NULLIF(TRIM(COALESCE(v_factura->>'caso', '')), '');

      IF v_caso_txt IS NOT NULL THEN
        SELECT id INTO v_caso_id
        FROM public.caso_precio_biblioteca
        WHERE nombre_caso = v_caso_txt
        LIMIT 1;
      ELSE
        v_caso_id := NULLIF(v_factura->>'caso_id', '')::BIGINT;
      END IF;

      SELECT COALESCE((f->>'lista_precio_id')::int, 1) INTO v_lista_factura
      FROM jsonb_array_elements(COALESCE(v_sesion.descuentos_lote->'facturas', '[]'::jsonb)) f
      WHERE (f->>'pp_id')::bigint IS NOT DISTINCT FROM v_pp_id
        AND f->>'marca' = v_marca_txt
        AND f->>'caso' = v_caso_txt
      LIMIT 1;

      IF v_lista_factura IS NULL THEN
        v_lista_factura := 1;
      END IF;

      v_fi_pares := COALESCE((v_factura->>'total_pares')::INTEGER, 0);
      v_fi_monto := COALESCE((v_factura->>'total_monto')::NUMERIC, 0);

      IF jsonb_typeof(v_factura->'items') <> 'array'
         OR jsonb_array_length(v_factura->'items') = 0 THEN
        RAISE EXCEPTION 'Factura PP=%, marca=%, caso=% sin items[]',
          COALESCE(v_pp_id::text, 'PE'), COALESCE(v_marca_txt, '∅'), COALESCE(v_caso_txt, '∅');
      END IF;

      IF v_pp_id_fi IS NULL THEN
        v_nro_fi := 'PE-' || v_pedido_id::TEXT || '-' || LPAD((v_total_fi + 1)::TEXT, 3, '0');
      ELSE
        v_nro_fi := generar_nro_factura_interna(v_pp_id_fi);
      END IF;

      INSERT INTO public.factura_interna (
        nro_factura, pp_id, pedido_id,
        cliente_id, vendedor_id, plazo_id, lista_precio_id,
        descuento_1, descuento_2, descuento_3, descuento_4,
        total_pares, total_monto, estado,
        marca, marca_id, caso, caso_id
      ) VALUES (
        v_nro_fi, v_pp_id_fi, v_pedido_id,
        p_cliente_id, p_vendedor_id, p_plazo_id, v_lista_factura,
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

        v_is_pe_ppd     := false;
        v_is_pe_staging := false;
        v_pe_stock_id   := NULL;

        IF v_is_pe_lote AND v_det_id IS NOT NULL THEN
          IF EXISTS (SELECT 1 FROM public.v_stock_pe_rimec vs WHERE vs.det_id = v_det_id) THEN
            v_is_pe_ppd := true;
          ELSIF v_det_id >= c_pe_det_base THEN
            v_is_pe_staging := true;
            v_pe_stock_id := v_det_id - c_pe_det_base;
          END IF;
        ELSIF v_det_id IS NOT NULL AND v_det_id >= c_pe_det_base THEN
          v_is_pe_staging := true;
          v_pe_stock_id := v_det_id - c_pe_det_base;
        END IF;

        v_is_pe_item := v_is_pe_ppd OR v_is_pe_staging;

        IF v_is_pe_ppd AND v_precio_payload IS NOT NULL THEN
          SELECT COALESCE(
            NULLIF(
              public.fn_precio_tier_vista(
                v_lista_factura, vs.lpn, vs.lpc02, vs.lpc03, vs.lpc04, vs.descp_caso
              ),
              0
            ),
            vs.lpn
          ) INTO v_precio_bd_lista
          FROM public.v_stock_pe_rimec vs
          WHERE vs.det_id = v_det_id;

          IF v_precio_bd_lista IS NULL THEN
            RAISE EXCEPTION 'Det PE ppd % perdió precio en v_stock_pe_rimec.', v_det_id;
          END IF;

          IF v_precio_bd_lista IS DISTINCT FROM v_precio_payload THEN
            RAISE EXCEPTION 'Precio cambió para PE ppd % (lista %): payload %, BD %.',
              v_det_id, v_lista_factura, v_precio_payload, v_precio_bd_lista;
          END IF;

        ELSIF v_is_pe_staging AND v_precio_payload IS NOT NULL THEN
          SELECT s.precio_unitario_gs::numeric INTO v_precio_bd_lista
          FROM public.stock_pronta_entrega_rimec s
          WHERE s.id = v_pe_stock_id;

          IF v_precio_bd_lista IS NULL THEN
            RETURN jsonb_build_object(
              'success', false,
              'error', format(
                'Stock PE staging id=%s no existe. Vacá el carrito y volvé a cargar desde catálogo.',
                COALESCE(v_pe_stock_id::text, '?')
              ),
              'detail', 'PE_STOCK_INEXISTENTE'
            );
          END IF;

          IF v_precio_bd_lista IS DISTINCT FROM v_precio_payload THEN
            RAISE EXCEPTION 'Precio cambió para PE staging % (LPN): payload %, BD %.',
              v_pe_stock_id, v_precio_payload, v_precio_bd_lista;
          END IF;

        ELSIF NOT v_is_pe_item AND v_det_id IS NOT NULL AND v_precio_payload IS NOT NULL THEN
          SELECT public.fn_precio_tier_vista(
            v_lista_factura, vs.lpn, vs.lpc02, vs.lpc03, vs.lpc04, vs.descp_caso
          ) INTO v_precio_bd_lista
          FROM public.v_stock_rimec vs
          WHERE vs.det_id = v_det_id;

          IF v_precio_bd_lista IS NULL OR v_precio_bd_lista <= 0 THEN
            RAISE EXCEPTION 'Det % perdió precio en BD entre VALIDAR y CONFIRMAR.', v_det_id;
          END IF;

          IF v_precio_bd_lista IS DISTINCT FROM v_precio_payload THEN
            RAISE EXCEPTION 'Precio cambió para det % (lista %): payload %, BD %.',
              v_det_id, v_lista_factura, v_precio_payload, v_precio_bd_lista;
          END IF;
        END IF;

        INSERT INTO public.factura_interna_detalle (
          factura_id, ppd_id, cajas, pares,
          precio_unit, precio_lista, precio_neto, subtotal,
          linea_snapshot
        ) VALUES (
          v_fi_id,
          CASE WHEN v_is_pe_staging THEN NULL ELSE v_det_id END,
          v_cajas, v_pares,
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
            'caso',         v_caso_txt,
            'origen_tipo',  CASE WHEN v_is_pe_item THEN 'PRONTA_ENTREGA' ELSE 'TRÁNSITO_PP' END
          )
        );

        IF v_is_pe_staging AND v_pares > 0 THEN
          UPDATE public.stock_pronta_entrega_rimec
          SET cantidad = GREATEST(0, cantidad - v_pares),
              updated_at = now()
          WHERE id = v_pe_stock_id
            AND cantidad >= v_pares;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'Stock PE staging insuficiente id=% (det %).', v_pe_stock_id, v_det_id;
          END IF;
        ELSIF v_det_id IS NOT NULL AND v_pares > 0 THEN
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
        'total_pares', v_fi_pares, 'total_monto', v_fi_monto,
        'origen_pe', v_is_pe_lote
      );
      v_total_fi := v_total_fi + 1;
    END LOOP;
  END LOOP;

  DELETE FROM public.carrito_item WHERE id_usuario = p_vendedor_id;
  DELETE FROM public.carrito_sesion WHERE id_usuario = p_vendedor_id;

  RETURN jsonb_build_object(
    'success', true,
    'nro_pedido', v_nro_pedido,
    'pedido_id', v_pedido_id,
    'total_facturas', v_total_fi,
    'facturas', v_facturas_out
  );
EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object('success', false, 'error', SQLERRM, 'detail', SQLSTATE);
END;
$function$;

COMMENT ON FUNCTION public.confirmar_pedido_web IS
  'MIG-155: PROMOCIONAL LPC03=LPN en validación confirmar · PE tier · CP tránsito';

COMMIT;

SELECT 'MIG-155 OK: confirmar_pedido_web promo LPC03' AS estado;
