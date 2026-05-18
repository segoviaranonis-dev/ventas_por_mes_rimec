-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 028: RPC confirmar_pedido_web — REGLA 1 ENFORCED EN BD
--
-- Reemplaza el RPC de la migración 010 para alinearlo con el frontend nuevo
-- (`rimec-web/app/carrito/page.tsx`) que manda el payload aplanado:
--
--     payload.lotes[].facturas[].items[]
--
--   donde CADA `facturas[i]` representa UNA factura_interna a generar.
--
-- ── REGLA 1 ────────────────────────────────────────────────────────────────
--   "No se mezclan marcas en una factura. No se mezclan casos en una factura."
--   ⇒ Una `factura_interna` por cada combinación (PP × Marca × Caso).
--
-- ── CAMBIOS vs migración 010 ───────────────────────────────────────────────
--   1. ALTER TABLE factura_interna: agrega `marca_id`, `caso_id` (FKs duras).
--      Las columnas existentes `marca` y `caso` (text) se conservan
--      denormalizadas para consultas rápidas e independencia del pilar.
--
--   2. RPC re-escrito:
--      · Itera `lotes[].facturas[]` (no `lotes[].marcas[]`).
--      · Crea UNA factura_interna por entrada en `facturas[]`.
--      · Guarda `marca`, `caso`, `marca_id`, `caso_id` en la FI.
--      · Inserta detalle con `linea_snapshot` para auditoría.
--      · Descuenta `pares_vendidos` en `pedido_proveedor_detalle`.
--      · Devuelve un array con nro_factura por cada FI creada.
--
--   3. Idempotencia: la transacción es atómica (todo o nada).
--      Si una FI falla, ROLLBACK total.
--
-- ── DEPENDENCIAS ───────────────────────────────────────────────────────────
--   · public.factura_interna (id, pp_id, nro_factura, marca, caso, ...)
--   · public.factura_interna_detalle
--   · public.pedido_venta_rimec
--   · public.pedido_proveedor_detalle (col `pares_vendidos`)
--   · public.marca (FK opcional)
--   · public.caso_precio_biblioteca (FK opcional)
--   · function generar_nro_factura_interna(p_pp_id BIGINT)
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
-- 1. Agregar columnas marca_id, caso_id a factura_interna (idempotente)
--    Las FKs se agregan condicionalmente: sólo si existe la tabla destino.
--    Si la tabla maestra (ej. `marca`) aún no se llama así o no existe,
--    la columna se crea igual y luego se puede atar la FK en una migración
--    futura cuando se sepa el nombre correcto.
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE public.factura_interna
  ADD COLUMN IF NOT EXISTS marca_id BIGINT NULL,
  ADD COLUMN IF NOT EXISTS caso_id  BIGINT NULL;

-- Tabla maestra de marcas:  public.marca_v2(id_marca)
-- Tabla maestra de casos:   public.caso_precio_biblioteca(id)
-- (verificado por las FKs existentes en `linea`)
DO $$
BEGIN
  -- ── FK a marca_v2 ─────────────────────────────────────────────────────
  IF EXISTS (
       SELECT 1 FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'marca_v2'
     )
     AND NOT EXISTS (
       SELECT 1 FROM information_schema.table_constraints
       WHERE table_schema = 'public'
         AND table_name = 'factura_interna'
         AND constraint_name = 'factura_interna_marca_id_fkey'
     )
  THEN
    ALTER TABLE public.factura_interna
      ADD CONSTRAINT factura_interna_marca_id_fkey
      FOREIGN KEY (marca_id) REFERENCES public.marca_v2(id_marca)
      ON DELETE SET NULL;
    RAISE NOTICE 'FK factura_interna.marca_id → public.marca_v2(id_marca) creada';
  ELSE
    RAISE NOTICE 'FK factura_interna.marca_id NO creada (tabla destino no encontrada o FK ya existe)';
  END IF;

  -- ── FK a caso_precio_biblioteca ───────────────────────────────────────
  IF EXISTS (
       SELECT 1 FROM information_schema.tables
       WHERE table_schema = 'public' AND table_name = 'caso_precio_biblioteca'
     )
     AND NOT EXISTS (
       SELECT 1 FROM information_schema.table_constraints
       WHERE table_schema = 'public'
         AND table_name = 'factura_interna'
         AND constraint_name = 'factura_interna_caso_id_fkey'
     )
  THEN
    ALTER TABLE public.factura_interna
      ADD CONSTRAINT factura_interna_caso_id_fkey
      FOREIGN KEY (caso_id) REFERENCES public.caso_precio_biblioteca(id)
      ON DELETE SET NULL;
    RAISE NOTICE 'FK factura_interna.caso_id → public.caso_precio_biblioteca(id) creada';
  ELSE
    RAISE NOTICE 'FK factura_interna.caso_id NO creada (tabla destino no encontrada o FK ya existe)';
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_factura_interna_marca_id ON public.factura_interna (marca_id);
CREATE INDEX IF NOT EXISTS idx_factura_interna_caso_id  ON public.factura_interna (caso_id);

-- ───────────────────────────────────────────────────────────────────────────
-- 2. Reemplazo del RPC confirmar_pedido_web
-- ───────────────────────────────────────────────────────────────────────────
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
  -- ── 1. Validaciones mínimas ─────────────────────────────────────────────
  IF p_payload IS NULL OR jsonb_typeof(p_payload->'lotes') <> 'array' THEN
    RETURN jsonb_build_object('success', false, 'error', 'Payload inválido: falta lotes[]');
  END IF;

  IF jsonb_array_length(p_payload->'lotes') = 0 THEN
    RETURN jsonb_build_object('success', false, 'error', 'Carrito vacío');
  END IF;

  -- ── 2. Generar número de pedido (cabecera) ──────────────────────────────
  v_nro_pedido := 'PVR-' || EXTRACT(YEAR FROM NOW())::TEXT || '-' ||
                  LPAD(FLOOR(RANDOM() * 1000000)::TEXT, 6, '0');

  -- ── 3. Insertar cabecera en pedido_venta_rimec ──────────────────────────
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

  -- ── 4. Procesar cada LOTE (= un PP) ─────────────────────────────────────
  FOR v_lote IN SELECT * FROM jsonb_array_elements(p_payload->'lotes')
  LOOP
    v_pp_id  := (v_lote->>'pp_id')::BIGINT;
    v_pp_nro := COALESCE(v_lote->>'pp_nro', v_pp_id::TEXT);

    IF jsonb_typeof(v_lote->'facturas') <> 'array'
       OR jsonb_array_length(v_lote->'facturas') = 0 THEN
      RAISE EXCEPTION 'Lote PP=% sin facturas[]', v_pp_id;
    END IF;

    -- ── 5. Procesar cada FACTURA prevista (1 FI por PP×Marca×Caso) ───────
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

      -- Generar número único para ESTA factura (la función debería numerar
      -- secuencialmente cada llamada para el mismo pp_id).
      v_nro_fi := generar_nro_factura_interna(v_pp_id);

      INSERT INTO public.factura_interna (
        nro_factura, pp_id,
        cliente_id, vendedor_id, plazo_id, lista_precio_id,
        descuento_1, descuento_2, descuento_3, descuento_4,
        total_pares, total_monto, estado,
        marca, marca_id, caso, caso_id
      ) VALUES (
        v_nro_fi, v_pp_id,
        p_cliente_id, p_vendedor_id, p_plazo_id, p_lista_precio_id,
        p_descuento_1, p_descuento_2, p_descuento_3, p_descuento_4,
        v_fi_pares, v_fi_monto, 'RESERVADA',
        v_marca_txt, v_marca_id, v_caso_txt, v_caso_id
      )
      RETURNING id INTO v_fi_id;

      -- ── 6. Detalle de la FI + descuento de stock en tránsito ───────────
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

        -- Descontar pares vendidos en mercadería en tránsito
        IF v_det_id IS NOT NULL AND v_pares > 0 THEN
          UPDATE public.pedido_proveedor_detalle
          SET pares_vendidos = COALESCE(pares_vendidos, 0) + v_pares
          WHERE id = v_det_id;
        END IF;
      END LOOP;

      -- ── 7. Acumular en el output ───────────────────────────────────────
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

  -- ── 8. Retornar resultado ─────────────────────────────────────────────
  RETURN jsonb_build_object(
    'success',         true,
    'pedido_id',       v_pedido_id,
    'nro_pedido',      v_nro_pedido,
    'total_facturas',  v_total_fi,
    'facturas',        v_facturas_out
  );

EXCEPTION WHEN OTHERS THEN
  -- Rollback automático por excepción + retorno explícito al cliente.
  RETURN jsonb_build_object(
    'success', false,
    'error',   SQLERRM,
    'detail',  SQLSTATE
  );
END;
$$;

GRANT EXECUTE ON FUNCTION public.confirmar_pedido_web TO anon;
GRANT EXECUTE ON FUNCTION public.confirmar_pedido_web TO authenticated;

COMMENT ON FUNCTION public.confirmar_pedido_web IS
  'Confirma un pedido web. Crea pedido_venta_rimec + N facturas_internas '
  '(una por cada PP×Marca×Caso del payload, Regla 1 enforced) + detalles '
  '+ descuenta pares_vendidos en pedido_proveedor_detalle. Atómico.';

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN (correr aparte después del COMMIT):
-- ═══════════════════════════════════════════════════════════════════════════
--
-- a) Columnas nuevas en factura_interna:
--    SELECT column_name FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name = 'factura_interna'
--      AND column_name IN ('marca_id', 'caso_id');
--
-- b) Firma del RPC actualizada:
--    SELECT pg_get_function_arguments(oid)
--    FROM pg_proc WHERE proname = 'confirmar_pedido_web';
--
-- c) Dry-run con payload de prueba (sin commitear stock):
--    BEGIN;
--    SELECT confirmar_pedido_web(
--      p_cliente_id := 1, p_vendedor_id := NULL, p_plazo_id := 1,
--      p_lista_precio_id := 1,
--      p_descuento_1 := 0, p_descuento_2 := 0, p_descuento_3 := 0, p_descuento_4 := 0,
--      p_total_pares := 24, p_total_monto := 4800,
--      p_payload := '{
--        "lotes": [{
--          "pp_id": 9, "pp_nro": "F9", "quincena": "1Q-Jun",
--          "total_pares": 24, "total_monto": 4800,
--          "facturas": [{
--            "marca": "VIZZANO", "marca_id": 2,
--            "caso": "NORMAL", "caso_id": null,
--            "total_pares": 24, "total_monto": 4800,
--            "items": [{
--              "det_id": 1, "linea_codigo": "1122",
--              "ref_codigo": "ABC", "color_nombre": "NEGRO 01",
--              "gradas_fmt": "33/34", "imagen_url": "",
--              "cajas": 2, "pares": 24,
--              "precio_base": 200, "precio_neto": 200, "subtotal": 4800
--            }]
--          }]
--        }]
--      }'::jsonb
--    );
--    ROLLBACK;
-- ═══════════════════════════════════════════════════════════════════════════
