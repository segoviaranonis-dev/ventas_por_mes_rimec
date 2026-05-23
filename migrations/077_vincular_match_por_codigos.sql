-- MIG-077 — Match por códigos denormalizados como segundo paso del snapshot.
-- Cierra el 8% restante donde la cadena referencia.linea_id ≠ linea.id resuelta,
-- pero precio_lista ya tiene la fila correcta con códigos textuales (MIG-055).
-- Doctrina: estructural, no parche. Usa columnas oficialmente denormalizadas en precio_lista.

BEGIN;

DROP FUNCTION IF EXISTS public.vincular_listado_a_pp(bigint, bigint, bigint);

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
  v_paso1 bigint := 0;
  v_paso2 bigint := 0;
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

  -- ────────────────────────────────────────────────────────────────
  -- PASO 1: snapshot por IDs (estricto). Cubre el grueso.
  -- ────────────────────────────────────────────────────────────────
  WITH fuente AS (
    SELECT
      ppd.id AS det_id,
      pl.lpn,
      pl.lpc02,
      pl.lpc03,
      pl.lpc04,
      pl.dolar_aplicado,
      (SELECT cpb.id FROM public.caso_precio_biblioteca cpb
        WHERE cpb.nombre_caso = pl.nombre_caso_aplicado LIMIT 1) AS caso_bib_id,
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
  SELECT COUNT(*) INTO v_paso1 FROM upd;

  -- ────────────────────────────────────────────────────────────────
  -- PASO 2: match por códigos denormalizados (MIG-055).
  -- Cubre PPDs cuyo referencia.linea_id no matchea (mismatch catálogo).
  -- precio_lista.linea_codigo / referencia_codigo son texto oficial.
  -- ────────────────────────────────────────────────────────────────
  WITH faltantes AS (
    SELECT
      ppd.id AS det_id,
      pp.id AS pp_id,
      TRIM(ppd.linea)        AS cod_linea,
      TRIM(ppd.referencia)   AS cod_ref,
      m.id                   AS material_id,
      public.fn_resolver_evento_precio_ppd(pp.id, ppd.id) AS evento_resuelto
    FROM public.pedido_proveedor_detalle ppd
    JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
    LEFT JOIN public.material m
      ON m.codigo_proveedor::text = ppd.material_code
     AND m.proveedor_id = pp.proveedor_importacion_id
    WHERE pp.id = p_pp_id
      AND ppd.precio_lpn IS NULL
      AND m.id IS NOT NULL
  ),
  match_codigos AS (
    SELECT DISTINCT ON (f.det_id)
      f.det_id,
      pl.lpn,
      pl.lpc02,
      pl.lpc03,
      pl.lpc04,
      pl.dolar_aplicado,
      (SELECT cpb.id FROM public.caso_precio_biblioteca cpb
        WHERE cpb.nombre_caso = pl.nombre_caso_aplicado LIMIT 1) AS caso_bib_id,
      pl.nombre_caso_aplicado,
      f.evento_resuelto
    FROM faltantes f
    JOIN public.precio_lista pl
      ON pl.evento_id    = f.evento_resuelto
     AND TRIM(pl.linea_codigo)      = f.cod_linea
     AND TRIM(pl.referencia_codigo) = f.cod_ref
     AND pl.material_id   = f.material_id
    WHERE pl.lpn IS NOT NULL
    ORDER BY f.det_id, pl.id
  ),
  upd2 AS (
    UPDATE public.pedido_proveedor_detalle ppd
    SET
      precio_lpn           = mc.lpn,
      precio_lpc02         = mc.lpc02,
      precio_lpc03         = mc.lpc03,
      precio_lpc04         = mc.lpc04,
      precio_dolar_origen  = mc.dolar_aplicado,
      biblioteca_id        = mc.caso_bib_id,
      listado_precio_id    = mc.evento_resuelto,
      descp_caso_snapshot  = mc.nombre_caso_aplicado,
      precio_vinculado_en  = now(),
      precio_vinculado_por = p_usuario_id
    FROM match_codigos mc
    WHERE ppd.id = mc.det_id
    RETURNING ppd.id
  )
  SELECT COUNT(*) INTO v_paso2 FROM upd2;

  SELECT COUNT(*)
  INTO v_sin_match
  FROM public.pedido_proveedor_detalle ppd
  WHERE ppd.pedido_proveedor_id = p_pp_id
    AND ppd.precio_lpn IS NULL
    AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0;

  RETURN jsonb_build_object(
    'success', true,
    'pp_id', p_pp_id,
    'evento_id', v_evento,
    'filas_paso1_ids', v_paso1,
    'filas_paso2_codigos', v_paso2,
    'filas_sin_match', v_sin_match,
    'detail', 'SNAPSHOT_OK_MIG077'
  );
END;
$function$;

COMMENT ON FUNCTION public.vincular_listado_a_pp(bigint, bigint, bigint) IS
  'MIG-077: snapshot precios PPD en 2 pasos. (1) match por IDs. (2) fallback estructural por códigos denormalizados de precio_lista.';

COMMIT;

SELECT 'MIG-077 OK: vincular_listado_a_pp con match por códigos' AS estado;
