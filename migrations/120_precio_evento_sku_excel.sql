-- 120 — SKUs Excel persistidos por evento (Report Paso 0 → Paso 3)
-- Paridad session Streamlit re_skus; fuente para staging + calcular_precio_lista_evento_sql

CREATE TABLE IF NOT EXISTS public.precio_evento_sku_excel (
  id            BIGSERIAL PRIMARY KEY,
  evento_id     BIGINT NOT NULL REFERENCES public.precio_evento(id) ON DELETE CASCADE,
  marca         TEXT NOT NULL DEFAULT '',
  linea         TEXT NOT NULL DEFAULT '',
  referencia    TEXT NOT NULL DEFAULT '',
  material      TEXT NOT NULL DEFAULT '',
  descripcion   TEXT NOT NULL DEFAULT '',
  fob_fabrica   NUMERIC(14, 4) NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_precio_evento_sku_excel_evento
  ON public.precio_evento_sku_excel (evento_id);

COMMENT ON TABLE public.precio_evento_sku_excel IS
  'SKUs leídos del Excel en Paso 0 Report; alimentan resolución pilares y precio_lista_staging.';
