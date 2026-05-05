-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 010: RPC para Confirmar Pedido desde Web
-- Flujo: Web (Confirmar) → RPC Supabase (Crea PVR + FI + Baja Stock)
--
-- Esta función es llamada desde el frontend y ejecuta todo en una transacción:
--   1. Inserta el pedido en pedido_venta_rimec
--   2. Por cada PP en el carrito, crea una factura_interna en estado RESERVADA
--   3. Inserta los detalles y descuenta stock de mercadería en tránsito
--   4. Retorna JSON con nro_pedido y las facturas generadas
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
-- Función RPC principal: confirmar_pedido_web
-- ───────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION confirmar_pedido_web(
  p_cliente_id      BIGINT,
  p_vendedor_id     BIGINT DEFAULT NULL,
  p_plazo_id        BIGINT DEFAULT NULL,
  p_lista_precio_id INTEGER DEFAULT 1,
  p_descuento_1     NUMERIC DEFAULT 0,
  p_descuento_2     NUMERIC DEFAULT 0,
  p_descuento_3     NUMERIC DEFAULT 0,
  p_descuento_4     NUMERIC DEFAULT 0,
  p_total_pares     INTEGER DEFAULT 0,
  p_total_monto     NUMERIC DEFAULT 0,
  p_payload         JSONB DEFAULT '{}'::JSONB
)
RETURNS JSONB AS $$
DECLARE
  v_nro_pedido      TEXT;
  v_pedido_id       BIGINT;
  v_lote            JSONB;
  v_marca_data      JSONB;
  v_item            JSONB;
  v_pp_id           BIGINT;
  v_pp_nro          TEXT;
  v_marca           TEXT;
  v_fi_id           BIGINT;
  v_nro_fi          TEXT;
  v_lote_pares      INTEGER;
  v_lote_monto      NUMERIC;
  v_facturas        JSONB := '[]'::JSONB;
  v_det_id          BIGINT;
  v_pares           INTEGER;
BEGIN
  -- ── 1. Generar número de pedido ────────────────────────────────────────
  v_nro_pedido := 'PVR-' || EXTRACT(YEAR FROM NOW())::TEXT || '-' || 
                  LPAD(FLOOR(RANDOM() * 1000000)::TEXT, 6, '0');

  -- ── 2. Insertar pedido en pedido_venta_rimec ───────────────────────────
  INSERT INTO pedido_venta_rimec (
    nro_pedido, cliente_id, vendedor_id, plazo_id, lista_precio_id,
    descuento_1, descuento_2, descuento_3, descuento_4,
    total_pares, total_monto, estado, payload_json
  ) VALUES (
    v_nro_pedido, p_cliente_id, p_vendedor_id, p_plazo_id, p_lista_precio_id,
    p_descuento_1, p_descuento_2, p_descuento_3, p_descuento_4,
    p_total_pares, p_total_monto, 'PENDIENTE', p_payload
  )
  RETURNING id INTO v_pedido_id;

  -- ── 3. Procesar cada lote (PP) del payload ─────────────────────────────
  FOR v_lote IN SELECT * FROM jsonb_array_elements(p_payload->'lotes')
  LOOP
    v_pp_id := (v_lote->>'pp_id')::BIGINT;
    v_pp_nro := COALESCE(v_lote->>'pp_nro', v_pp_id::TEXT);
    v_lote_pares := 0;
    v_lote_monto := 0;

    -- Calcular totales del lote
    FOR v_marca_data IN SELECT * FROM jsonb_array_elements(v_lote->'marcas')
    LOOP
      v_lote_pares := v_lote_pares + COALESCE((v_marca_data->>'total_pares')::INTEGER, 0);
      v_lote_monto := v_lote_monto + COALESCE((v_marca_data->>'total_monto')::NUMERIC, 0);
    END LOOP;

    -- Generar número de factura interna
    v_nro_fi := generar_nro_factura_interna(v_pp_id);

    -- Crear factura interna en estado RESERVADA
    INSERT INTO factura_interna (
      nro_factura, pp_id, cliente_id, vendedor_id, plazo_id, lista_precio_id,
      descuento_1, descuento_2, descuento_3, descuento_4,
      total_pares, total_monto, estado
    ) VALUES (
      v_nro_fi, v_pp_id, p_cliente_id, p_vendedor_id, p_plazo_id, p_lista_precio_id,
      p_descuento_1, p_descuento_2, p_descuento_3, p_descuento_4,
      v_lote_pares, v_lote_monto, 'RESERVADA'
    )
    RETURNING id INTO v_fi_id;

    -- ── 4. Procesar items de cada marca ────────────────────────────────────
    FOR v_marca_data IN SELECT * FROM jsonb_array_elements(v_lote->'marcas')
    LOOP
      v_marca := COALESCE(v_marca_data->>'marca', 'SIN_MARCA');
      
      FOR v_item IN SELECT * FROM jsonb_array_elements(v_marca_data->'items')
      LOOP
        v_det_id := (v_item->>'det_id')::BIGINT;
        v_pares := COALESCE((v_item->>'pares')::INTEGER, 0);

        -- Insertar detalle de factura interna
        INSERT INTO factura_interna_detalle (
          factura_id, ppd_id, pares, cajas,
          precio_unit, subtotal, precio_neto, linea_snapshot
        ) VALUES (
          v_fi_id,
          v_det_id,
          v_pares,
          COALESCE((v_item->>'cajas')::INTEGER, 0),
          COALESCE((v_item->>'precio_neto')::NUMERIC, 0),
          COALESCE((v_item->>'subtotal')::NUMERIC, 0),
          COALESCE((v_item->>'precio_neto')::NUMERIC, 0),
          jsonb_build_object(
            'linea_codigo', v_item->>'linea_codigo',
            'ref_codigo', v_item->>'ref_codigo',
            'color_nombre', v_item->>'color_nombre',
            'gradas_fmt', v_item->>'gradas_fmt',
            'imagen_url', v_item->>'imagen_url'
          )
        );

        -- ── 5. Descontar stock de mercadería en tránsito ─────────────────
        IF v_det_id IS NOT NULL AND v_pares > 0 THEN
          UPDATE pedido_proveedor_detalle
          SET pares_vendidos = COALESCE(pares_vendidos, 0) + v_pares
          WHERE id = v_det_id;
        END IF;
      END LOOP;
    END LOOP;

    -- Agregar factura al array de respuesta
    v_facturas := v_facturas || jsonb_build_object(
      'fi_id', v_fi_id,
      'nro_factura', v_nro_fi,
      'pp_id', v_pp_id,
      'total_pares', v_lote_pares,
      'total_monto', v_lote_monto
    );
  END LOOP;

  -- ── 6. Retornar resultado ──────────────────────────────────────────────
  RETURN jsonb_build_object(
    'success', true,
    'pedido_id', v_pedido_id,
    'nro_pedido', v_nro_pedido,
    'facturas', v_facturas
  );

EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object(
    'success', false,
    'error', SQLERRM
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Dar permisos para que el cliente anon/authenticated pueda llamar la función
GRANT EXECUTE ON FUNCTION confirmar_pedido_web TO anon;
GRANT EXECUTE ON FUNCTION confirmar_pedido_web TO authenticated;

COMMIT;
