-- 099_v_factura_interna_preventa_global.sql
-- Numeracion global de preventas/FI sin tocar la clave historica `nro_factura`.
--
-- `nro_factura` queda como documento legacy usado por traspasos/movimientos.
-- `numero_preventa_global` es el numero visible global: PV000001..infinito.

CREATE OR REPLACE VIEW public.v_factura_interna_preventa AS
SELECT
  fi.*,
  fi.nro_factura AS nro_factura_legacy,
  (
    'PV' ||
    LPAD(
      ROW_NUMBER() OVER (ORDER BY fi.id)::text,
      6,
      '0'
    )
  ) AS numero_preventa_global
FROM public.factura_interna fi;

GRANT SELECT ON public.v_factura_interna_preventa TO anon;
GRANT SELECT ON public.v_factura_interna_preventa TO authenticated;
