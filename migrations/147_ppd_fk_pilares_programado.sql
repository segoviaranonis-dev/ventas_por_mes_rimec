-- MIG-147 — pedido_proveedor_detalle: FK pilares L·R (PROGRAMADO · prefactura molécula)

BEGIN;

ALTER TABLE public.pedido_proveedor_detalle
  ADD COLUMN IF NOT EXISTS linea_id bigint REFERENCES public.linea (id),
  ADD COLUMN IF NOT EXISTS referencia_id bigint REFERENCES public.referencia (id);

CREATE INDEX IF NOT EXISTS idx_ppd_linea_id ON public.pedido_proveedor_detalle (linea_id)
  WHERE linea_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ppd_referencia_id ON public.pedido_proveedor_detalle (referencia_id)
  WHERE referencia_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ppd_pp_pilares ON public.pedido_proveedor_detalle (
  pedido_proveedor_id,
  linea_id,
  referencia_id,
  id_material
) WHERE linea_id IS NOT NULL;

COMMENT ON COLUMN public.pedido_proveedor_detalle.linea_id IS
  'FK pilar línea — PROGRAMADO post-import proforma (MIG-147)';

COMMENT ON COLUMN public.pedido_proveedor_detalle.referencia_id IS
  'FK pilar referencia — PROGRAMADO post-import proforma (MIG-147)';

COMMIT;
