-- MIG-073 — Columnas de snapshot inmutable en pedido_proveedor_detalle
-- Contrato Héctor: precios congelados al vincular; la web lee PPD, no precio_lista.

BEGIN;

ALTER TABLE public.pedido_proveedor_detalle
  ADD COLUMN IF NOT EXISTS precio_lpn numeric NULL,
  ADD COLUMN IF NOT EXISTS precio_lpc02 numeric NULL,
  ADD COLUMN IF NOT EXISTS precio_lpc03 numeric NULL,
  ADD COLUMN IF NOT EXISTS precio_lpc04 numeric NULL,
  ADD COLUMN IF NOT EXISTS precio_dolar_origen numeric NULL,
  ADD COLUMN IF NOT EXISTS biblioteca_id bigint NULL
    REFERENCES public.caso_precio_biblioteca(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS listado_precio_id bigint NULL
    REFERENCES public.precio_evento(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS descp_caso_snapshot text NULL,
  ADD COLUMN IF NOT EXISTS precio_vinculado_en timestamptz NULL,
  ADD COLUMN IF NOT EXISTS precio_vinculado_por bigint NULL
    REFERENCES public.usuario_v2(id_usuario) ON DELETE SET NULL;

COMMENT ON COLUMN public.pedido_proveedor_detalle.precio_lpn IS
  'MIG-073: LPN congelado al vincular listado. Fuente única para catálogo web.';
COMMENT ON COLUMN public.pedido_proveedor_detalle.biblioteca_id IS
  'MIG-073: FK a caso_precio_biblioteca (regla/caso origen del snapshot).';
COMMENT ON COLUMN public.pedido_proveedor_detalle.listado_precio_id IS
  'MIG-073: FK a precio_evento usado al congelar precios.';

CREATE INDEX IF NOT EXISTS idx_ppd_listado_precio
  ON public.pedido_proveedor_detalle (listado_precio_id)
  WHERE listado_precio_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ppd_precio_lpn_vigente
  ON public.pedido_proveedor_detalle (pedido_proveedor_id)
  WHERE precio_lpn IS NOT NULL;

COMMIT;

SELECT 'MIG-073 OK: columnas snapshot en pedido_proveedor_detalle' AS estado;
