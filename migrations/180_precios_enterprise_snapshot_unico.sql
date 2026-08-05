-- MIG-180 — Precios enterprise: una sola verdad · snapshot obligatorio · cert G7/G8
-- Director · 2026-07-25 · paridad Excel (MIG-179) · sin fallback LPN×factor en runtime
--
-- Cadena: motor FOB → precio_lista → PPD snapshot → vista/Web/FI
-- apply_ley solo PROMO (MIG-179). Consumo: tier almacenado; sin recalcular LPC desde LPN.

BEGIN;

-- ── 1. Backfill precio_lista tiers (ley Excel desde fob×índice) ───────────────
UPDATE public.precio_lista pl
SET
  lpn = public.redondear_centena_gs(pl.fob_ajustado * pl.indice_aplicado),
  lpc03 = CASE
    WHEN UPPER(TRIM(COALESCE(pl.nombre_caso_aplicado, ''))) = 'PROMOCIONAL' THEN
      public.redondear_centena_gs(pl.fob_ajustado * pl.indice_aplicado)
    WHEN pl.lpc03 IS NOT NULL OR pl.lpc04 IS NOT NULL THEN
      public.redondear_centena_gs(pl.fob_ajustado * pl.indice_aplicado * 1.12)
    ELSE pl.lpc03
  END,
  lpc04 = CASE
    WHEN UPPER(TRIM(COALESCE(pl.nombre_caso_aplicado, ''))) = 'PROMOCIONAL' THEN
      public.redondear_centena_gs(pl.fob_ajustado * pl.indice_aplicado)
    WHEN pl.lpc04 IS NOT NULL THEN
      public.redondear_centena_gs(pl.fob_ajustado * pl.indice_aplicado * 1.20)
    ELSE pl.lpc04
  END
WHERE pl.fob_ajustado IS NOT NULL
  AND pl.fob_ajustado > 0
  AND pl.indice_aplicado IS NOT NULL
  AND pl.indice_aplicado > 0;

-- ── 2. fn_precio_tier_vista — FAIL-CLOSED: solo snapshot, sin LPN×factor ─────
CREATE OR REPLACE FUNCTION public.fn_precio_tier_vista(
  p_lista integer,
  p_lpn numeric,
  p_lpc02 numeric,
  p_lpc03 numeric,
  p_lpc04 numeric,
  p_descp_caso text
)
RETURNS numeric
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE p_lista
    WHEN 1 THEN public.redondear_centena_gs(p_lpn)
    WHEN 2 THEN public.redondear_centena_gs(p_lpc02)
    WHEN 3 THEN
      CASE
        WHEN UPPER(TRIM(COALESCE(p_descp_caso, ''))) = 'PROMOCIONAL' THEN
          public.redondear_centena_gs(p_lpn)
        WHEN COALESCE(p_lpc03, 0) > 0 THEN
          public.redondear_centena_gs(p_lpc03)
        ELSE NULL
      END
    WHEN 4 THEN
      CASE
        WHEN UPPER(TRIM(COALESCE(p_descp_caso, ''))) = 'PROMOCIONAL' THEN
          public.redondear_centena_gs(p_lpn)
        WHEN COALESCE(p_lpc04, 0) > 0 THEN
          public.redondear_centena_gs(p_lpc04)
        ELSE NULL
      END
    ELSE public.redondear_centena_gs(p_lpn)
  END;
$$;

COMMENT ON FUNCTION public.fn_precio_tier_vista(integer, numeric, numeric, numeric, numeric, text) IS
  'MIG-180: tier desde snapshot PPD/pl · PROMO=LPN · sin LPN×1.12 fallback.';

-- ── 3. Reparación masiva PPD CP desde listado canónico ───────────────────────
CREATE OR REPLACE FUNCTION public.reparar_snapshot_tiers_cp(p_pp_id bigint DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_pp bigint;
  v_total bigint := 0;
  v_results jsonb := '[]'::jsonb;
BEGIN
  FOR v_pp IN
    SELECT pp.id
    FROM public.pedido_proveedor pp
    WHERE pp.estado_transito = 'EN_TRANSITO'
      AND (p_pp_id IS NULL OR pp.id = p_pp_id)
    ORDER BY pp.id
  LOOP
    v_results := v_results || public.sincronizar_precios_vinculados_cp(v_pp);
    v_total := v_total + 1;
  END LOOP;

  RETURN jsonb_build_object(
    'success', true,
    'pps_procesados', v_total,
    'detalle', v_results,
    'detail', 'REPARAR_SNAPSHOT_TIERS_MIG180'
  );
END;
$$;

-- ── 4. Certificación G7/G8 — drift LPC + fantasma LPN-only ───────────────────
CREATE OR REPLACE FUNCTION public.certificar_precios_cp_rimec(p_pp_id bigint DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SET search_path = public
AS $function$
DECLARE
  v_g1 int := 0;
  v_g2 int := 0;
  v_g3 int := 0;
  v_g4 int := 0;
  v_g5 int := 0;
  v_g7 int := 0;
  v_g8 int := 0;
  v_view_ok boolean := false;
  v_pp_ids bigint[];
BEGIN
  SELECT COALESCE(array_agg(pp.id ORDER BY pp.id), ARRAY[]::bigint[])
  INTO v_pp_ids
  FROM public.pedido_proveedor pp
  WHERE pp.estado_transito = 'EN_TRANSITO'
    AND COALESCE(pp.categoria_id, (
      SELECT ic.categoria_id FROM public.intencion_compra_pedido icp
      JOIN public.intencion_compra ic ON ic.id = icp.intencion_compra_id
      WHERE icp.pedido_proveedor_id = pp.id ORDER BY icp.id LIMIT 1
    )) = 2
    AND (p_pp_id IS NULL OR pp.id = p_pp_id);

  SELECT COUNT(*)::int INTO v_g1
  FROM public.pedido_proveedor_detalle ppd
  JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
  WHERE pp.id = ANY(v_pp_ids)
    AND ppd.referencia IS NOT NULL
    AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
    AND COALESCE(ppd.precio_lpn, 0) <= 0;

  SELECT COUNT(*)::int INTO v_g2
  FROM public.v_stock_rimec v
  JOIN public.pedido_proveedor_detalle ppd ON ppd.id = v.det_id
  WHERE v.pp_id = ANY(v_pp_ids)
    AND ppd.precio_lpn IS DISTINCT FROM v.lpn;

  SELECT COUNT(*)::int INTO v_g3
  FROM public.pedido_proveedor_detalle ppd
  JOIN public.pedido_proveedor p ON p.id = ppd.pedido_proveedor_id
  JOIN public.intencion_compra_pedido icp ON icp.pedido_proveedor_id = p.id AND icp.precio_evento_id IS NOT NULL
  LEFT JOIN public.linea l ON l.codigo_proveedor::text = TRIM(ppd.linea) AND l.proveedor_id = p.proveedor_importacion_id
  LEFT JOIN public.material m ON m.codigo_proveedor::text = TRIM(ppd.material_code) AND m.proveedor_id = p.proveedor_importacion_id
  LEFT JOIN public.referencia ref ON ref.codigo_proveedor::text = TRIM(ppd.referencia) AND ref.linea_id = l.id
  LEFT JOIN LATERAL public._pl_canonico_cp(icp.precio_evento_id, l.id, ref.id, m.id) pc ON true
  WHERE p.id = ANY(v_pp_ids)
    AND icp.id = (SELECT icp2.id FROM public.intencion_compra_pedido icp2
                  WHERE icp2.pedido_proveedor_id = p.id AND icp2.precio_evento_id IS NOT NULL
                  ORDER BY icp2.id LIMIT 1)
    AND pc.lpn IS NOT NULL
    AND ppd.precio_lpn IS DISTINCT FROM pc.lpn;

  -- G7: PPD lpc03/lpc04 ≠ listado canónico (Excel)
  SELECT COUNT(*)::int INTO v_g7
  FROM public.pedido_proveedor_detalle ppd
  JOIN public.pedido_proveedor p ON p.id = ppd.pedido_proveedor_id
  JOIN public.intencion_compra_pedido icp ON icp.pedido_proveedor_id = p.id AND icp.precio_evento_id IS NOT NULL
  LEFT JOIN public.linea l ON l.codigo_proveedor::text = TRIM(ppd.linea) AND l.proveedor_id = p.proveedor_importacion_id
  LEFT JOIN public.material m ON m.codigo_proveedor::text = TRIM(ppd.material_code) AND m.proveedor_id = p.proveedor_importacion_id
  LEFT JOIN public.referencia ref ON ref.codigo_proveedor::text = TRIM(ppd.referencia) AND ref.linea_id = l.id
  LEFT JOIN LATERAL public._pl_canonico_cp(icp.precio_evento_id, l.id, ref.id, m.id) pc ON true
  WHERE p.id = ANY(v_pp_ids)
    AND icp.id = (SELECT icp2.id FROM public.intencion_compra_pedido icp2
                  WHERE icp2.pedido_proveedor_id = p.id AND icp2.precio_evento_id IS NOT NULL
                  ORDER BY icp2.id LIMIT 1)
    AND pc.lpn IS NOT NULL
    AND (
      (pc.lpc03 IS NOT NULL AND ppd.precio_lpc03 IS DISTINCT FROM pc.lpc03)
      OR (pc.lpc04 IS NOT NULL AND ppd.precio_lpc04 IS DISTINCT FROM pc.lpc04)
    );

  -- G8: fantasma LPN-only (lpc03 = centena(lpn×1.12) pero ≠ listado Excel)
  SELECT COUNT(*)::int INTO v_g8
  FROM public.pedido_proveedor_detalle ppd
  JOIN public.pedido_proveedor p ON p.id = ppd.pedido_proveedor_id
  JOIN public.intencion_compra_pedido icp ON icp.pedido_proveedor_id = p.id AND icp.precio_evento_id IS NOT NULL
  LEFT JOIN public.linea l ON l.codigo_proveedor::text = TRIM(ppd.linea) AND l.proveedor_id = p.proveedor_importacion_id
  LEFT JOIN public.material m ON m.codigo_proveedor::text = TRIM(ppd.material_code) AND m.proveedor_id = p.proveedor_importacion_id
  LEFT JOIN public.referencia ref ON ref.codigo_proveedor::text = TRIM(ppd.referencia) AND ref.linea_id = l.id
  LEFT JOIN LATERAL public._pl_canonico_cp(icp.precio_evento_id, l.id, ref.id, m.id) pc ON true
  WHERE p.id = ANY(v_pp_ids)
    AND icp.id = (SELECT icp2.id FROM public.intencion_compra_pedido icp2
                  WHERE icp2.pedido_proveedor_id = p.id AND icp2.precio_evento_id IS NOT NULL
                  ORDER BY icp2.id LIMIT 1)
    AND UPPER(TRIM(COALESCE(ppd.descp_caso_snapshot, ''))) IS DISTINCT FROM 'PROMOCIONAL'
    AND pc.lpc03 IS NOT NULL
    AND ppd.precio_lpn IS NOT NULL AND ppd.precio_lpn > 0
    AND ppd.precio_lpc03 = public.redondear_centena_gs(ppd.precio_lpn * 1.12)
    AND ppd.precio_lpc03 IS DISTINCT FROM pc.lpc03;

  SELECT COUNT(*)::int INTO v_g4
  FROM public.factura_interna fi
  JOIN public.factura_interna_detalle fid ON fid.factura_id = fi.id
  JOIN public.pedido_proveedor_detalle ppd ON ppd.id = fid.ppd_id
  WHERE fi.pp_id = ANY(v_pp_ids)
    AND UPPER(TRIM(fi.estado)) IN ('RESERVADA', 'CONFIRMADA')
    AND COALESCE(ppd.precio_lpn, 0) > 0
    AND fid.precio_unit IS NOT NULL
    AND fid.precio_unit NOT IN (
      ppd.precio_lpn,
      COALESCE(ppd.precio_lpc02, ppd.precio_lpn),
      COALESCE(ppd.precio_lpc03, ppd.precio_lpn),
      COALESCE(ppd.precio_lpc04, ppd.precio_lpn)
    );

  SELECT COUNT(*)::int INTO v_g5
  FROM public.carrito_item ci
  JOIN public.v_stock_rimec v ON v.det_id = ci.det_id
  WHERE v.pp_id = ANY(v_pp_ids)
    AND COALESCE(v.lpn, 0) > 0
    AND ci.precio_snapshot IS DISTINCT FROM v.lpn;

  SELECT NOT (pg_get_viewdef('public.v_stock_rimec'::regclass, true) ~ 'pl\.lpn')
  INTO v_view_ok;

  RETURN jsonb_build_object(
    'ok', (v_g1 + v_g2 + v_g4 + v_g5 + v_g7 + v_g8 = 0 AND v_view_ok),
    'listado_drift', v_g3,
    'ts', NOW(),
    'pp_ids', v_pp_ids,
    'gates', jsonb_build_object(
      'G1_ppd_sin_lpn', v_g1,
      'G2_web_vs_ppd', v_g2,
      'G3_ppd_vs_listado_lpn', v_g3,
      'G4_fi_vs_ppd', v_g4,
      'G5_carrito_vs_web', v_g5,
      'G6_vista_solo_ppd', v_view_ok,
      'G7_ppd_vs_listado_lpc', v_g7,
      'G8_fantasma_lpn_only', v_g8
    )
  );
END;
$function$;

COMMENT ON FUNCTION public.certificar_precios_cp_rimec(bigint) IS
  'MIG-180: 8 gates · G7 LPC drift · G8 LPN-only ghost · ok=false si cualquier gate duro >0.';

COMMIT;

SELECT 'MIG-180 OK: enterprise snapshot + cert G7/G8' AS estado;
