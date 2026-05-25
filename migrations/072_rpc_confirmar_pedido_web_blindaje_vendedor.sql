-- MIG-072 — RPC confirmar_pedido_web con validaciones estructurales de identidad.
-- Reemplaza definitivamente el archivo huérfano mig_070_rpc_confirmar_pedido_web.sql
-- que vivía fuera del pipeline numerado.
-- Agrega validaciones que faltaban:
--   1. p_vendedor_id NOT NULL
--   2. p_cliente_id NOT NULL
--   3. vendedor existe en usuario_v2 con rol VENDEDOR o ADMIN
-- Conserva la lógica de resolución de caso_id desde caso_precio_biblioteca por nombre_caso.

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
  p_payload         jsonb   DEFAULT '{}'::jsonb
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
BEGIN
  -- ── 0. Validación de identidad del operador (NUEVO MIG-072) ─────────────
  IF p_vendedor_id IS NULL THEN
    RETURN jsonb_build_object(
      'success', false,
      'error',   'p_vendedor_id es obligatorio. La sesión de venta debe identificar al vendedor.',
      'detail',  'VENDEDOR_FALTANTE'
    );
  END IF;

  IF p_cliente_id IS NULL THEN
    RETURN jsonb_build_object(
      'success', false,
      'error',   'p_cliente_id es obligatorio.',
      'detail',  'CLIENTE_FALTANTE'
    );
  END IF;

  PERFORM 1 FROM public.usuario_v2 u
  WHERE u.id_usuario = p_vendedor_id
    AND public.fn_es_usuario_vendedor_o_admin(u.id_usuario);

  IF NOT FOUND THEN
    RETURN jsonb_build_object(
      'success', false,
      'error',   format('Usuario %s no existe o no tiene rol VENDEDOR/ADMIN.', p_vendedor_id),
      'detail',  'VENDEDOR_INVALIDO'
    );
  END IF;

  -- ── 1. Validación de payload ─────────────────────────────────────────────
  IF p_payload IS NULL OR jsonb_typeof(p_payload->'lotes') <> 'array' THEN
    RETURN jsonb_build_object('success', false, 'error', 'Payload inválido: falta lotes[]');
  END IF;

  IF jsonb_array_length(p_payload->'lotes') = 0 THEN
    RETURN jsonb_build_object('success', false, 'error', 'Carrito vacío');
  END IF;

  -- ── 2. Generar número de pedido ─────────────────────────────────────────
  v_nro_pedido := 'PVR-' || EXTRACT(YEAR FROM NOW())::TEXT || '-' ||
                  LPAD(FLOOR(RANDOM() * 1000000)::TEXT, 6, '0');

  -- ── 3. Insertar cabecera ────────────────────────────────────────────────
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

  -- ── 4. Procesar cada lote (= un PP) ─────────────────────────────────────
  FOR v_lote IN SELECT * FROM jsonb_array_elements(p_payload->'lotes')
  LOOP
    v_pp_id  := (v_lote->>'pp_id')::BIGINT;
    v_pp_nro := COALESCE(v_lote->>'pp_nro', v_pp_id::TEXT);

    IF jsonb_typeof(v_lote->'facturas') <> 'array'
       OR jsonb_array_length(v_lote->'facturas') = 0 THEN
      RAISE EXCEPTION 'Lote PP=% sin facturas[]', v_pp_id;
    END IF;

    -- ── 5. Procesar cada FI (1 por PP×Marca×Caso) ─────────────────────────
    FOR v_factura IN SELECT * FROM jsonb_array_elements(v_lote->'facturas')
    LOOP
      v_marca_txt := NULLIF(TRIM(COALESCE(v_factura->>'marca', '')), '');
      v_marca_id  := NULLIF(v_factura->>'marca_id', '')::BIGINT;
      v_caso_txt  := NULLIF(TRIM(COALESCE(v_factura->>'caso', '')), '');

      -- Resolver caso_id desde caso_precio_biblioteca usando el nombre del caso
      -- para evitar errores de FK (la vista entrega ids de precio_evento_caso
      -- que no coinciden con caso_precio_biblioteca.id).
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

      -- ── 6. Detalle FI + descuento de stock ───────────────────────────────
      FOR v_item IN SELECT * FROM jsonb_array_elements(v_factura->'items')
      LOOP
        v_det_id := NULLIF(v_item->>'det_id', '')::BIGINT;
        v_pares  := COALESCE((v_item->>'pares')::INTEGER, 0);
        v_cajas  := COALESCE((v_item->>'cajas')::INTEGER, 0);

        INSERT INTO public.factura_interna_detalle (
          factura_id, ppd_id, cajas, pares,
          precio_unit, precio_lista, precio_neto, subtotal,
          linea_snapshot
        ) VALUES (
          v_fi_id,
          v_det_id,
          v_cajas,
          v_pares,
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
            RAISE EXCEPTION 'No hay suficiente stock para L% R% (Lote: %). Solicitado: % pares, Disponible: % pares.',
              v_item->>'linea_codigo',
              v_item->>'ref_codigo',
              v_pp_nro,
              v_pares,
              (v_db_cantidad_pares - v_db_pares_vendidos);
          END IF;

          UPDATE public.pedido_proveedor_detalle
          SET pares_vendidos = COALESCE(pares_vendidos, 0) + v_pares
          WHERE id = v_det_id;
        END IF;
      END LOOP;

      v_facturas_out := v_facturas_out || jsonb_build_object(
        'fi_id',       v_fi_id,
        'nro_factura', v_nro_fi,
        'pp_id',       v_pp_id,
        'pp_nro',      v_pp_nro,
        'marca',       v_marca_txt,
        'marca_id',    v_marca_id,
        'caso',        v_caso_txt,
        'caso_id',     v_caso_id,
        'total_pares', v_fi_pares,
        'total_monto', v_fi_monto
      );
      v_total_fi := v_total_fi + 1;
    END LOOP;
  END LOOP;

  RETURN jsonb_build_object(
    'success',         true,
    'pedido_id',       v_pedido_id,
    'nro_pedido',      v_nro_pedido,
    'total_facturas',  v_total_fi,
    'facturas',        v_facturas_out
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
  'MIG-072: validación estructural de identidad (vendedor_id NOT NULL + rol VENDEDOR/ADMIN). Resolución de caso_id desde caso_precio_biblioteca por nombre_caso. Reemplaza al archivo huérfano mig_070_rpc_confirmar_pedido_web.sql.';
