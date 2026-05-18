-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 029: FK formal entre factura_interna y pedido_venta_rimec
--
-- Contexto:
--   La 028 dejó la asociación pedido→FIs implícita (por ventana de tiempo en
--   `created_at`). Eso funciona para demos pero es frágil.
--   Esta migración formaliza la relación con una FK dura `pedido_id`.
--
-- Cambios:
--   1. Garantiza que la columna `factura_interna.pedido_id` existe (idempotente).
--   2. Backfilla `pedido_id` en FIs viejas (matchea por ventana de ±10s).
--   3. Crea índice para acelerar `/pedidos`.
--   4. Re-CREATE OR REPLACE del RPC `confirmar_pedido_web` para SETEAR `pedido_id`.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. Columna pedido_id (idempotente) ──────────────────────────────────────
ALTER TABLE public.factura_interna
  ADD COLUMN IF NOT EXISTS pedido_id BIGINT NULL;

-- FK condicional (si no existe ya)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public'
      AND table_name='factura_interna'
      AND constraint_name='factura_interna_pedido_id_fkey'
  ) THEN
    ALTER TABLE public.factura_interna
      ADD CONSTRAINT factura_interna_pedido_id_fkey
      FOREIGN KEY (pedido_id) REFERENCES public.pedido_venta_rimec(id)
      ON DELETE SET NULL;
    RAISE NOTICE 'FK factura_interna.pedido_id creada';
  ELSE
    RAISE NOTICE 'FK factura_interna.pedido_id ya existía';
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_factura_interna_pedido_id
  ON public.factura_interna (pedido_id);

-- ── 2. Backfill: matchea FIs viejas (sin pedido_id) por ventana de tiempo ──
WITH match AS (
  SELECT
    fi.id AS fi_id,
    (SELECT pvr.id
       FROM public.pedido_venta_rimec pvr
       WHERE ABS(EXTRACT(EPOCH FROM (fi.created_at - pvr.created_at))) < 10
       ORDER BY ABS(EXTRACT(EPOCH FROM (fi.created_at - pvr.created_at)))
       LIMIT 1) AS pvr_id
  FROM public.factura_interna fi
  WHERE fi.pedido_id IS NULL
)
UPDATE public.factura_interna fi
SET pedido_id = m.pvr_id
FROM match m
WHERE fi.id = m.fi_id
  AND m.pvr_id IS NOT NULL;


-- ── 3. RPC actualizado ─────────────────────────────────────────────────────
-- (Sólo cambia el INSERT en factura_interna para incluir `pedido_id`)
CREATE OR REPLACE FUNCTION public.confirmar_pedido_web(
  p_cliente_id      BIGINT,
  p_vendedor_id     BIGINT  DEFAULT NULL,
  p_plazo_id        BIGINT  DEFAULT NULL,
  p_lista_precio_id INTEGER DEFAULT 1,
  p_descuento_1     NUMERIC DEFAULT 0,
  p_descuento_2     NUMERIC DEFAULT 0,
  p_descuento_3     NUMERIC DEFAULT 0,
  p_descuento_4     NUMERIC DEFAULT 0,
  p_total_pares     INTEGER DEFAULT 0,
  p_total_monto     NUMERIC DEFAULT 0,
  p_payload         JSONB   DEFAULT '{}'::JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
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
BEGIN
  IF p_payload IS NULL OR jsonb_typeof(p_payload->'lotes') <> 'array' THEN
    RETURN jsonb_build_object('success', false, 'error', 'Payload inválido: falta lotes[]');
  END IF;
  IF jsonb_array_length(p_payload->'lotes') = 0 THEN
    RETURN jsonb_build_object('success', false, 'error', 'Carrito vacío');
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

  FOR v_lote IN SELECT * FROM jsonb_array_elements(p_payload->'lotes')
  LOOP
    v_pp_id  := (v_lote->>'pp_id')::BIGINT;
    v_pp_nro := COALESCE(v_lote->>'pp_nro', v_pp_id::TEXT);

    IF jsonb_typeof(v_lote->'facturas') <> 'array'
       OR jsonb_array_length(v_lote->'facturas') = 0 THEN
      RAISE EXCEPTION 'Lote PP=% sin facturas[]', v_pp_id;
    END IF;

    FOR v_factura IN SELECT * FROM jsonb_array_elements(v_lote->'facturas')
    LOOP
      v_marca_txt := NULLIF(TRIM(COALESCE(v_factura->>'marca', '')), '');
      v_marca_id  := NULLIF(v_factura->>'marca_id', '')::BIGINT;
      v_caso_txt  := NULLIF(TRIM(COALESCE(v_factura->>'caso', '')), '');
      v_caso_id   := NULLIF(v_factura->>'caso_id', '')::BIGINT;
      v_fi_pares  := COALESCE((v_factura->>'total_pares')::INTEGER, 0);
      v_fi_monto  := COALESCE((v_factura->>'total_monto')::NUMERIC, 0);

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
        'pedido_id',   v_pedido_id,
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
$$;

GRANT EXECUTE ON FUNCTION public.confirmar_pedido_web TO anon;
GRANT EXECUTE ON FUNCTION public.confirmar_pedido_web TO authenticated;

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN:
-- ═══════════════════════════════════════════════════════════════════════════
-- SELECT
--   COUNT(*)                                  AS total_fi,
--   COUNT(*) FILTER (WHERE pedido_id IS NULL) AS sin_pedido,
--   COUNT(DISTINCT pedido_id)                 AS pedidos_con_fi
-- FROM public.factura_interna;
-- ═══════════════════════════════════════════════════════════════════════════
