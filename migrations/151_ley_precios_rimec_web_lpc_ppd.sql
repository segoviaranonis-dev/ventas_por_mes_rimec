-- MIG-151 · Ley precios RIMEC Web — LPC03/LPC04 aritmética sobre LPN en PPD
-- Director 2026-07-15 · NO modifica motor precio_lista
--
-- Regla:
--   caso != PROMOCIONAL:
--     precio_lpc03 = ROUND(precio_lpn * 1.12)
--     precio_lpc04 = ROUND(precio_lpn * 1.20)
--   caso = PROMOCIONAL:
--     precio_lpc03 = precio_lpn
--     precio_lpc04 = precio_lpn
--
-- LPC02 no se toca (sigue del motor/vínculo).

CREATE OR REPLACE FUNCTION public.apply_ley_precios_rimec_web_ppd(
  p_pp_id bigint DEFAULT NULL
)
RETURNS TABLE(filas_actualizadas bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  n_arith bigint := 0;
  n_promo bigint := 0;
BEGIN
  UPDATE public.pedido_proveedor_detalle ppd
  SET
    precio_lpc03 = ROUND(ppd.precio_lpn * 1.12),
    precio_lpc04 = ROUND(ppd.precio_lpn * 1.20)
  WHERE ppd.precio_lpn IS NOT NULL
    AND ppd.precio_lpn > 0
    AND (
      p_pp_id IS NULL
      OR ppd.pedido_proveedor_id = p_pp_id
    )
    AND UPPER(TRIM(COALESCE(ppd.descp_caso_snapshot, ''))) IS DISTINCT FROM 'PROMOCIONAL';

  GET DIAGNOSTICS n_arith = ROW_COUNT;

  -- Promo: LPN = LPC03 = LPC04
  UPDATE public.pedido_proveedor_detalle ppd
  SET
    precio_lpc03 = ppd.precio_lpn,
    precio_lpc04 = ppd.precio_lpn
  WHERE ppd.precio_lpn IS NOT NULL
    AND ppd.precio_lpn > 0
    AND (
      p_pp_id IS NULL
      OR ppd.pedido_proveedor_id = p_pp_id
    )
    AND UPPER(TRIM(COALESCE(ppd.descp_caso_snapshot, ''))) = 'PROMOCIONAL';

  GET DIAGNOSTICS n_promo = ROW_COUNT;

  filas_actualizadas := n_arith + n_promo;
  RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.apply_ley_precios_rimec_web_ppd(bigint) IS
  'Ley RIMEC Web: LPC03=LPN*1.12 LPC04=LPN*1.20; PROMO LPN=LPC03=LPC04. Motor intacto.';

SELECT * FROM public.apply_ley_precios_rimec_web_ppd(NULL);
