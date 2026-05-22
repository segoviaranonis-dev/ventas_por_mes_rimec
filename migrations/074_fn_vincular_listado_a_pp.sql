-- MIG-074 — Congelar precios de precio_lista → pedido_proveedor_detalle
-- Reglas: solo PP ABIERTO; bloqueado si hay pares_vendidos > 0 (compromiso en calle).

BEGIN;

CREATE OR REPLACE FUNCTION public.fn_resolver_evento_precio_ppd(
  p_pp_id bigint,
  p_det_id bigint
)
RETURNS bigint
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT icp2.precio_evento_id
  FROM public.intencion_compra_pedido icp2
  JOIN public.intencion_compra ic2 ON ic2.id = icp2.intencion_compra_id
  JOIN public.pedido_proveedor_detalle ppd ON ppd.id = p_det_id
  WHERE icp2.pedido_proveedor_id = p_pp_id
    AND icp2.precio_evento_id IS NOT NULL
    AND (
      ppd.id_marca IS NULL
      OR ic2.id_marca = ppd.id_marca::bigint
    )
  ORDER BY
    CASE
      WHEN ppd.id_marca IS NOT NULL AND ic2.id_marca = ppd.id_marca::bigint THEN 0
      ELSE 1
    END,
    icp2.id
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.vincular_listado_a_pp(
  p_pp_id bigint,
  p_evento_id bigint DEFAULT NULL,
  p_usuario_id bigint DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $function$
DECLARE
  v_estado text;
  v_evento bigint;
  v_comprometidos bigint;
  v_actualizados bigint;
  v_sin_match bigint;
BEGIN
  SELECT UPPER(TRIM(pp.estado))
  INTO v_estado
  FROM public.pedido_proveedor pp
  WHERE pp.id = p_pp_id;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('success', false, 'error', 'PP no existe', 'detail', 'PP_INEXISTENTE');
  END IF;

  IF v_estado IS DISTINCT FROM 'ABIERTO' THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('PP en estado %s. Solo ABIERTO permite re-vincular snapshot.', v_estado),
      'detail', 'PP_NO_ABIERTO'
    );
  END IF;

  SELECT COUNT(*)
  INTO v_comprometidos
  FROM public.pedido_proveedor_detalle ppd
  WHERE ppd.pedido_proveedor_id = p_pp_id
    AND COALESCE(ppd.pares_vendidos, 0) > 0;

  IF v_comprometidos > 0 THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('PP tiene %s líneas con ventas comprometidas (pares_vendidos > 0). Snapshot congelado.', v_comprometidos),
      'detail', 'PP_CON_VENTAS_CALLE'
    );
  END IF;

  v_evento := COALESCE(
    p_evento_id,
    (
      SELECT DISTINCT icp.precio_evento_id
      FROM public.intencion_compra_pedido icp
      WHERE icp.pedido_proveedor_id = p_pp_id
        AND icp.precio_evento_id IS NOT NULL
      ORDER BY icp.precio_evento_id
      LIMIT 1
    )
  );

  IF v_evento IS NULL THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', 'El PP no tiene precio_evento_id en intencion_compra_pedido.',
      'detail', 'SIN_EVENTO_PRECIO'
    );
  END IF;

  WITH fuente AS (
    SELECT
      ppd.id AS det_id,
      pl.lpn,
      pl.lpc02,
      pl.lpc03,
      pl.lpc04,
      pl.dolar_aplicado,
      pl.caso_id AS caso_bib_id,
      pl.nombre_caso_aplicado,
      public.fn_resolver_evento_precio_ppd(pp.id, ppd.id) AS evento_resuelto
    FROM public.pedido_proveedor_detalle ppd
    JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
    LEFT JOIN public.material m
      ON m.codigo_proveedor::text = ppd.material_code
     AND m.proveedor_id = pp.proveedor_importacion_id
    LEFT JOIN public.linea l
      ON l.codigo_proveedor::text = ppd.linea
     AND l.proveedor_id = pp.proveedor_importacion_id
    LEFT JOIN public.referencia ref_j
      ON ref_j.codigo_proveedor::text = ppd.referencia
     AND ref_j.linea_id = l.id
    LEFT JOIN public.precio_lista pl
      ON pl.evento_id = public.fn_resolver_evento_precio_ppd(pp.id, ppd.id)
     AND pl.linea_id = COALESCE(l.id, ref_j.linea_id)
     AND pl.referencia_id = ref_j.id
     AND pl.material_id = m.id
    WHERE pp.id = p_pp_id
  ),
  upd AS (
    UPDATE public.pedido_proveedor_detalle ppd
    SET
      precio_lpn           = f.lpn,
      precio_lpc02         = f.lpc02,
      precio_lpc03         = f.lpc03,
      precio_lpc04         = f.lpc04,
      precio_dolar_origen  = f.dolar_aplicado,
      biblioteca_id        = f.caso_bib_id,
      listado_precio_id    = f.evento_resuelto,
      descp_caso_snapshot  = f.nombre_caso_aplicado,
      precio_vinculado_en  = now(),
      precio_vinculado_por = p_usuario_id
    FROM fuente f
    WHERE ppd.id = f.det_id
      AND f.lpn IS NOT NULL
      AND f.evento_resuelto = v_evento
    RETURNING ppd.id
  )
  SELECT COUNT(*) INTO v_actualizados FROM upd;

  SELECT COUNT(*)
  INTO v_sin_match
  FROM public.pedido_proveedor_detalle ppd
  WHERE ppd.pedido_proveedor_id = p_pp_id
    AND ppd.precio_lpn IS NULL;

  RETURN jsonb_build_object(
    'success', true,
    'pp_id', p_pp_id,
    'evento_id', v_evento,
    'filas_actualizadas', v_actualizados,
    'filas_sin_match', v_sin_match,
    'detail', 'SNAPSHOT_OK'
  );
END;
$function$;

COMMENT ON FUNCTION public.vincular_listado_a_pp(bigint, bigint, bigint) IS
  'MIG-074: congela precio_lista → PPD. Solo PP ABIERTO sin pares_vendidos.';

COMMIT;

SELECT 'MIG-074 OK: vincular_listado_a_pp + fn_resolver_evento_precio_ppd' AS estado;
