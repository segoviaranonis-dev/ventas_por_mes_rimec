-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 006: Factura Interna + Stock Bazar + Tipo Cliente
-- ORDEN_FIN_DE_SEMANA — Bloque 1-3
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
-- 1. tipo en cliente_v2
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE cliente_v2
  ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'MAYORISTA'
  CHECK (tipo IN ('MAYORISTA', 'MINORISTA'));

-- ───────────────────────────────────────────────────────────────────────────
-- 2. usuario_id en vendedor_v2 (fix null vendedor rimec-web)
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE vendedor_v2
  ADD COLUMN IF NOT EXISTS usuario_id UUID REFERENCES auth.users(id);

CREATE INDEX IF NOT EXISTS idx_vendedor_usuario_id
  ON vendedor_v2 (usuario_id);

-- ───────────────────────────────────────────────────────────────────────────
-- 3. estado_arribo + fecha_arribo en pedido_proveedor
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE pedido_proveedor
  ADD COLUMN IF NOT EXISTS estado_arribo TEXT DEFAULT 'EN_TRANSITO'
    CHECK (estado_arribo IN ('EN_TRANSITO', 'ARRIBADO')),
  ADD COLUMN IF NOT EXISTS fecha_arribo DATE;

-- ───────────────────────────────────────────────────────────────────────────
-- 4. pares_vendidos en pedido_proveedor_detalle
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE pedido_proveedor_detalle
  ADD COLUMN IF NOT EXISTS pares_vendidos INTEGER DEFAULT 0;

-- ───────────────────────────────────────────────────────────────────────────
-- 5. factura_interna
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factura_interna (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nro             TEXT NOT NULL,
  pp_id           BIGINT NOT NULL REFERENCES pedido_proveedor(id),
  cliente_id      BIGINT NOT NULL REFERENCES cliente_v2(id),
  vendedor_id     BIGINT REFERENCES vendedor_v2(id),
  plazo_id        BIGINT REFERENCES plazo_v2(id),
  lista_precio_id INTEGER NOT NULL,
  descuento_1     NUMERIC DEFAULT 0,
  descuento_2     NUMERIC DEFAULT 0,
  descuento_3     NUMERIC DEFAULT 0,
  descuento_4     NUMERIC DEFAULT 0,
  total_pares     INTEGER NOT NULL,
  total_neto      NUMERIC NOT NULL,
  estado          TEXT NOT NULL DEFAULT 'CONFIRMADA'
                  CHECK (estado IN ('CONFIRMADA', 'ANULADA')),
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fi_pp_id
  ON factura_interna (pp_id);

CREATE INDEX IF NOT EXISTS idx_fi_cliente_id
  ON factura_interna (cliente_id);

-- ───────────────────────────────────────────────────────────────────────────
-- 6. factura_interna_detalle
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS factura_interna_detalle (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  factura_id  BIGINT NOT NULL REFERENCES factura_interna(id) ON DELETE CASCADE,
  ppd_id      BIGINT NOT NULL,   -- pedido_proveedor_detalle.id
  pares       INTEGER NOT NULL,
  cajas       INTEGER NOT NULL DEFAULT 0,
  precio_unit NUMERIC NOT NULL,
  subtotal    NUMERIC NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fid_factura_id
  ON factura_interna_detalle (factura_id);

CREATE INDEX IF NOT EXISTS idx_fid_ppd_id
  ON factura_interna_detalle (ppd_id);

-- ───────────────────────────────────────────────────────────────────────────
-- 7. Función descontar_stock_pp (usa det_id directo)
-- ───────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION descontar_stock_pp(
  p_det_id BIGINT,
  p_pares  INTEGER
) RETURNS void AS $$
BEGIN
  UPDATE pedido_proveedor_detalle
  SET pares_vendidos = COALESCE(pares_vendidos, 0) + p_pares
  WHERE id = p_det_id
    AND (cantidad_pares - COALESCE(pares_vendidos, 0)) >= p_pares;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Stock insuficiente para det_id=%', p_det_id;
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMIT;
