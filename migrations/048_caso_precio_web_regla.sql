-- 048 — OT-WEB-PRECIO-509-001: Diccionario casos → precio venta Bazar Web (LPN + markup)
-- Crea tabla caso_precio_web_regla + función fn_precio_venta_web

-- D1: Tabla diccionario markup por caso
CREATE TABLE IF NOT EXISTS caso_precio_web_regla (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  caso_codigo     TEXT NOT NULL,          -- match exacto trim upper con nombre_caso_aplicado
  markup_pct      NUMERIC(5,2) NOT NULL,  -- 50.00 = +50%
  descripcion     TEXT,
  activo          BOOLEAN NOT NULL DEFAULT true,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_caso_precio_web_codigo UNIQUE (caso_codigo),
  CONSTRAINT chk_markup_nonneg CHECK (markup_pct >= 0)
);

COMMENT ON TABLE caso_precio_web_regla IS
  'OT-509: Diccionario editable markup web por caso comercial. Usado por fn_precio_venta_web.';

-- D2: Seed inicial — 5 casos usuario + DEFAULT
INSERT INTO caso_precio_web_regla (caso_codigo, markup_pct, descripcion, activo)
VALUES
  ('BR-VZ-MD-ML-MKA-O', 50.00, 'Línea Brasil estándar +50%', true),
  ('ACT-BRSPORT', 50.00, 'Activewear BRSport +50%', true),
  ('CARTERAS', 40.00, 'Carteras +40%', true),
  ('CHINELO', 40.00, 'Chinelos +40%', true),
  ('PROMOCIONAL', 40.00, 'Promocionales +40%', true),
  ('DEFAULT', 50.00, 'Fallback si caso desconocido +50%', true)
ON CONFLICT (caso_codigo) DO NOTHING;

-- D3: Función calcular precio venta web
CREATE OR REPLACE FUNCTION fn_precio_venta_web(p_lpn NUMERIC, p_caso TEXT)
RETURNS NUMERIC
LANGUAGE SQL
STABLE
AS $$
  SELECT
    -- Redondeo a centena (política web RIMEC)
    ROUND(
      p_lpn * (1 + COALESCE(markup_pct, 50.00) / 100.0) / 1000.0
    ) * 1000.0
  FROM caso_precio_web_regla
  WHERE UPPER(TRIM(caso_codigo)) = UPPER(TRIM(COALESCE(p_caso, 'DEFAULT')))
    AND activo = true
  LIMIT 1;
$$;

COMMENT ON FUNCTION fn_precio_venta_web IS
  'OT-509: Calcula precio venta web = LPN × (1 + markup%). Redondea a centena. Fallback DEFAULT si caso no existe.';
