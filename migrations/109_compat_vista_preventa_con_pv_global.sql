-- MIG-109: Compatibilidad vista preventa con pv_global
-- Vista lee de columna física pv_global (NO ROW_NUMBER dinámico)

BEGIN;

DROP VIEW IF EXISTS public.v_factura_interna_preventa CASCADE;

CREATE OR REPLACE VIEW public.v_factura_interna_preventa AS
SELECT
  fi.*,
  fi.nro_factura AS nro_factura_legacy,
  CASE
    WHEN fi.pv_global IS NOT NULL
    THEN 'PV' || LPAD(fi.pv_global::text, 6, '0')
    ELSE fi.nro_factura
  END AS numero_preventa_global
FROM public.factura_interna fi;

GRANT SELECT ON public.v_factura_interna_preventa TO anon;
GRANT SELECT ON public.v_factura_interna_preventa TO authenticated;

COMMIT;
