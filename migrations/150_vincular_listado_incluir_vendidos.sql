-- MIG-150 — Vincular listado: modo tránsito vs TODOS (incl. PPD 100% vendidas).
-- p_incluir_vendidos = false → MIG-139 (solo saldo > 0)
-- p_incluir_vendidos = true  → actualiza TODAS las filas PPD con match de precio
--                               (mercadería aún no llegó al país · corrección listado erróneo)

BEGIN;

DROP FUNCTION IF EXISTS public.vincular_listado_a_pp(bigint, bigint, bigint);
DROP FUNCTION IF EXISTS public.vincular_listado_a_pp(bigint, bigint, bigint, boolean);

CREATE OR REPLACE FUNCTION public.vincular_listado_a_pp(
  p_pp_id bigint,
  p_evento_id bigint DEFAULT NULL,
  p_usuario_id bigint DEFAULT NULL,
  p_incluir_vendidos boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $function$
DECLARE
  v_estado text;
  v_evento bigint;
  v_congeladas bigint := 0;
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
  INTO v_congeladas
  FROM public.pedido_proveedor_detalle ppd
  WHERE ppd.pedido_proveedor_id = p_pp_id
    AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) = 0
    AND COALESCE(ppd.pares_vendidos, 0) > 0;

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
      (SELECT cpb.id FROM public.caso_precio_biblioteca cpb
        WHERE cpb.nombre_caso = pl.nombre_caso_aplicado LIMIT 1) AS caso_bib_id,
      pl.nombre_caso_aplicado
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
      ON pl.evento_id = v_evento
     AND pl.linea_id = COALESCE(l.id, ref_j.linea_id)
     AND pl.referencia_id = ref_j.id
     AND pl.material_id = m.id
    WHERE pp.id = p_pp_id
      AND (
        p_incluir_vendidos
        OR GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
      )
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
      listado_precio_id    = v_evento,
      descp_caso_snapshot  = f.nombre_caso_aplicado,
      precio_vinculado_en  = now(),
      precio_vinculado_por = p_usuario_id
    FROM fuente f
    WHERE ppd.id = f.det_id
      AND f.lpn IS NOT NULL
    RETURNING ppd.id
  )
  SELECT COUNT(*) INTO v_paso1 FROM upd;

  WITH faltantes AS (
    SELECT
      ppd.id AS det_id,
      TRIM(ppd.linea)      AS cod_linea,
      TRIM(ppd.referencia) AS cod_ref,
      m.id                 AS material_id
    FROM public.pedido_proveedor_detalle ppd
    JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
    LEFT JOIN public.material m
      ON m.codigo_proveedor::text = ppd.material_code
     AND m.proveedor_id = pp.proveedor_importacion_id
    WHERE pp.id = p_pp_id
      AND ppd.precio_lpn IS NULL
      AND m.id IS NOT NULL
      AND (
        p_incluir_vendidos
        OR GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
      )
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
      pl.nombre_caso_aplicado
    FROM faltantes f
    JOIN public.precio_lista pl
      ON pl.evento_id = v_evento
     AND TRIM(pl.linea_codigo)      = f.cod_linea
     AND TRIM(pl.referencia_codigo) = f.cod_ref
     AND pl.material_id = f.material_id
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
      listado_precio_id    = v_evento,
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
    AND (
      p_incluir_vendidos
      OR GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
    );

  RETURN jsonb_build_object(
    'success', true,
    'pp_id', p_pp_id,
    'evento_id', v_evento,
    'incluir_vendidos', p_incluir_vendidos,
    'filas_paso1_ids', v_paso1,
    'filas_paso2_codigos', v_paso2,
    'filas_sin_match', v_sin_match,
    'filas_congeladas_venta', CASE WHEN p_incluir_vendidos THEN 0 ELSE v_congeladas END,
    'filas_vendidas_forzadas', CASE WHEN p_incluir_vendidos THEN v_congeladas ELSE 0 END,
    'actualizados', v_paso1 + v_paso2,
    'detail', CASE
      WHEN p_incluir_vendidos THEN 'SNAPSHOT_OK_MIG150_TODOS_INCL_VENDIDOS'
      ELSE 'SNAPSHOT_OK_MIG150_SOLO_TRANSITO'
    END
  );
END;
$function$;

COMMENT ON FUNCTION public.vincular_listado_a_pp(bigint, bigint, bigint, boolean) IS
  'MIG-150: p_incluir_vendidos=false solo tránsito (saldo>0); true = todas las filas PPD incl. 100% vendidas.';

COMMIT;

SELECT 'MIG-150 OK: vincular_listado_a_pp incluir_vendidos' AS estado;
