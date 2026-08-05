-- MIG-114: fecha_confirmacion — Report Aprobaciones (canónico, robusto)
-- Idempotente. Trigger garantiza fecha aunque el cliente omita el SET.

-- 1. Columna
ALTER TABLE public.factura_interna
  ADD COLUMN IF NOT EXISTS fecha_confirmacion TIMESTAMPTZ;

COMMENT ON COLUMN public.factura_interna.fecha_confirmacion IS
  'Timestamp RESERVADA→CONFIRMADA. Report /aprobaciones — CSV + UI. Trigger trg_fi_fecha_confirmacion.';

-- 2. Backfill histórico CONFIRMADA
UPDATE public.factura_interna
SET fecha_confirmacion = COALESCE(created_at, NOW())
WHERE estado = 'CONFIRMADA'
  AND fecha_confirmacion IS NULL;

-- 3. Índices (CSV general + listado confirmadas)
CREATE INDEX IF NOT EXISTS idx_fi_fecha_confirmacion_desc
  ON public.factura_interna (fecha_confirmacion DESC NULLS LAST)
  WHERE estado = 'CONFIRMADA';

CREATE INDEX IF NOT EXISTS idx_fi_aprobaciones_csv_sort
  ON public.factura_interna (
    COALESCE(fecha_confirmacion, created_at) DESC NULLS LAST,
    id DESC
  )
  WHERE estado IN ('RESERVADA', 'CONFIRMADA', 'ANULADA');

CREATE INDEX IF NOT EXISTS idx_fi_detalle_factura_id
  ON public.factura_interna_detalle (factura_id);

-- 4. Trigger — BD como única verdad (no depender solo del cliente Report)
CREATE OR REPLACE FUNCTION public.fi_set_fecha_confirmacion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.estado = 'CONFIRMADA' THEN
    IF TG_OP = 'INSERT' OR (OLD.estado IS DISTINCT FROM 'CONFIRMADA') THEN
      IF NEW.fecha_confirmacion IS NULL THEN
        NEW.fecha_confirmacion := NOW();
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fi_fecha_confirmacion ON public.factura_interna;

CREATE TRIGGER trg_fi_fecha_confirmacion
  BEFORE INSERT OR UPDATE OF estado, fecha_confirmacion
  ON public.factura_interna
  FOR EACH ROW
  EXECUTE FUNCTION public.fi_set_fecha_confirmacion();
