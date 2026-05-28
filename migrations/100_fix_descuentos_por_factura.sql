-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 100: FIX - Descuentos Específicos por Factura
-- FECHA: 2026-05-28
-- DESCRIPCIÓN: Corrige confirmar_pedido_web() para usar descuentos específicos
--              de cada factura (PP×Marca×Caso) en lugar de descuentos globales.
--
-- PROBLEMA: Todas las FIs se creaban con los mismos descuentos globales,
--           ignorando los descuentos específicos configurados por el vendedor.
--
-- SOLUCIÓN: Leer descuentos de cada factura desde payload.facturas[].descuento_*
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
-- Función RPC actualizada: confirmar_pedido_web
-- Ahora usa descuentos específicos de cada factura desde el payload
-- ───────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION confirmar_pedido_web(
  p_cliente_id      BIGINT,
  p_vendedor_id     BIGINT DEFAULT NULL,
  p_plazo_id        BIGINT DEFAULT NULL,
  p_lista_precio_id INTEGER DEFAULT 1,
  p_descuento_1     NUMERIC DEFAULT 0,  -- Mantener para retrocompatibilidad
  p_descuento_2     NUMERIC DEFAULT 0,
  p_descuento_3     NUMERIC DEFAULT 0,
  p_descuento_4     NUMERIC DEFAULT 0,
  p_total_pares     INTEGER DEFAULT 0,
  p_total_monto     NUMERIC DEFAULT 0,
  p_payload         JSONB DEFAULT '{}'::JSONB,
  p_validacion_token UUID DEFAULT NULL  -- Token de validación (opcional)
)
RETURNS JSONB AS $$
DECLARE
  v_nro_pedido      TEXT;
  v_pedido_id       BIGINT;
  v_lote            JSONB;
  v_factura_data    JSONB;
  v_item            JSONB;
  v_pp_id           BIGINT;
  v_pp_nro          TEXT;
  v_marca           TEXT;
  v_caso            TEXT;
  v_fi_id           BIGINT;
  v_nro_fi          TEXT;
  v_factura_pares   INTEGER;
  v_factura_monto   NUMERIC;
  v_facturas_result JSONB := '[]'::JSONB;
  v_det_id          BIGINT;
  v_pares           INTEGER;
  v_quincena_id     BIGINT;
  -- Variables para descuentos específicos por factura
  v_desc1           NUMERIC;
  v_desc2           NUMERIC;
  v_desc3           NUMERIC;
  v_desc4           NUMERIC;
  v_lista_factura   INTEGER;
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

    -- Obtener quincena_arribo_id si existe
    v_quincena_id := NULL;
    IF v_lote ? 'quincena_id' THEN
      v_quincena_id := (v_lote->>'quincena_id')::BIGINT;
    END IF;

    -- ── 4. Procesar cada FACTURA (PP × Marca × Caso) ────────────────────
    FOR v_factura_data IN SELECT * FROM jsonb_array_elements(v_lote->'facturas')
    LOOP
      v_marca := COALESCE(v_factura_data->>'marca', 'SIN_MARCA');
      v_caso := COALESCE(v_factura_data->>'caso', 'SIN_CASO');
      v_factura_pares := COALESCE((v_factura_data->>'total_pares')::INTEGER, 0);
      v_factura_monto := COALESCE((v_factura_data->>'total_monto')::NUMERIC, 0);

      -- ✅ NUEVO: Leer descuentos específicos de esta factura
      v_desc1 := COALESCE((v_factura_data->>'descuento_1')::NUMERIC, p_descuento_1, 0);
      v_desc2 := COALESCE((v_factura_data->>'descuento_2')::NUMERIC, p_descuento_2, 0);
      v_desc3 := COALESCE((v_factura_data->>'descuento_3')::NUMERIC, p_descuento_3, 0);
      v_desc4 := COALESCE((v_factura_data->>'descuento_4')::NUMERIC, p_descuento_4, 0);
      v_lista_factura := COALESCE((v_factura_data->>'lista_precio_id')::INTEGER, p_lista_precio_id, 1);

      -- Generar número de factura interna
      v_nro_fi := generar_nro_factura_interna(v_pp_id);

      -- ✅ Crear factura interna con descuentos ESPECÍFICOS
      INSERT INTO factura_interna (
        nro_factura, pedido_id, pp_id, marca, caso,
        cliente_id, vendedor_id, plazo_id, lista_precio_id,
        descuento_1, descuento_2, descuento_3, descuento_4,
        total_pares, total_monto, estado, quincena_arribo_id
      ) VALUES (
        v_nro_fi, v_pedido_id, v_pp_id, v_marca, v_caso,
        p_cliente_id, p_vendedor_id, p_plazo_id, v_lista_factura,
        v_desc1, v_desc2, v_desc3, v_desc4,  -- ✅ Descuentos específicos
        v_factura_pares, v_factura_monto, 'RESERVADA', v_quincena_id
      )
      RETURNING id INTO v_fi_id;

      -- ── 5. Procesar items de la factura ────────────────────────────────
      FOR v_item IN SELECT * FROM jsonb_array_elements(v_factura_data->'items')
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
          COALESCE((v_item->>'precio_base')::NUMERIC, 0),  -- precio_unit = precio base
          COALESCE((v_item->>'subtotal')::NUMERIC, 0),
          COALESCE((v_item->>'precio_neto')::NUMERIC, 0),  -- precio con descuentos
          jsonb_build_object(
            'linea_codigo', v_item->>'linea_codigo',
            'ref_codigo', v_item->>'ref_codigo',
            'color_nombre', v_item->>'color_nombre',
            'gradas_fmt', v_item->>'gradas_fmt',
            'imagen_url', v_item->>'imagen_url'
          )
        );

        -- ── 6. Descontar stock de mercadería en tránsito ─────────────────
        IF v_det_id IS NOT NULL AND v_pares > 0 THEN
          PERFORM descontar_stock_pp(v_det_id, v_pares);
        END IF;
      END LOOP;

      -- Agregar factura al array de respuesta
      v_facturas_result := v_facturas_result || jsonb_build_object(
        'fi_id', v_fi_id,
        'nro_factura', v_nro_fi,
        'pp_id', v_pp_id,
        'marca', v_marca,
        'caso', v_caso,
        'total_pares', v_factura_pares,
        'total_monto', v_factura_monto
      );
    END LOOP;
  END LOOP;

  -- ── 7. Retornar resultado ──────────────────────────────────────────────
  RETURN jsonb_build_object(
    'success', true,
    'pedido_id', v_pedido_id,
    'nro_pedido', v_nro_pedido,
    'facturas', v_facturas_result
  );

EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object(
    'success', false,
    'error', SQLERRM
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION confirmar_pedido_web IS
  'MIG-100: Crea pedido_venta_rimec y facturas_interna usando descuentos específicos por factura';

COMMIT;

SELECT 'MIG-100 OK: confirmar_pedido_web con descuentos específicos por factura' AS estado;
