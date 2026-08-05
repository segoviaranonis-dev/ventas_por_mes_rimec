-- MIG-158 — vincular_biblioteca_a_pe: batch case-insensitive + fail si batch sin PP
-- Copia canónica: report/migrations/158_vincular_biblioteca_pe_batch_ci.sql

BEGIN;

CREATE OR REPLACE FUNCTION public.vincular_biblioteca_a_pe(
  p_biblioteca_precio_id bigint,
  p_usuario_id bigint DEFAULT NULL,
  p_numero_proforma text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $function$
DECLARE
  v_bib_nombre text;
  v_actualizados bigint := 0;
  v_promo bigint := 0;
  v_sin_caso bigint := 0;
  v_pp_locked bigint := 0;
  v_batch_norm text := NULLIF(lower(btrim(p_numero_proforma)), '');
BEGIN
  IF p_biblioteca_precio_id IS NULL OR p_biblioteca_precio_id <= 0 THEN
    RETURN jsonb_build_object('success', false, 'error', 'biblioteca_precio_id inválido', 'detail', 'BIB_INVALIDA');
  END IF;

  SELECT bp.nombre INTO v_bib_nombre
  FROM public.biblioteca_precio bp
  WHERE bp.id = p_biblioteca_precio_id;

  IF NOT FOUND THEN
    RETURN jsonb_build_object('success', false, 'error', 'Biblioteca no existe', 'detail', 'BIB_NO_EXISTE');
  END IF;

  WITH pe_pp AS (
    SELECT pp.id AS pp_id
    FROM public.pedido_proveedor pp
    JOIN public.quincena_arribo qa ON qa.id = pp.quincena_arribo_id
    WHERE pp.entidad_comercial = 'STOCK'
      AND pp.deposito_codigo IS NOT NULL
      AND pp.estado_transito = 'EN_DEPOSITO'
      AND pp.categoria_id = 1
      AND lower(trim(qa.descripcion)) = lower('Pronta entrega')
      AND (
        v_batch_norm IS NULL
        OR lower(btrim(pp.numero_proforma)) = v_batch_norm
      )
  ),
  map_linea_caso AS (
    SELECT
      l.proveedor_id,
      l.codigo_proveedor::text AS linea_cod,
      cpb.id AS caso_bib_id,
      cpb.nombre_caso
    FROM public.biblioteca_caso_linea bcl
    JOIN public.linea l ON l.id = bcl.linea_id
    JOIN public.caso_precio_biblioteca cpb ON cpb.id = bcl.caso_biblioteca_id
    WHERE bcl.biblioteca_id = p_biblioteca_precio_id
      AND COALESCE(cpb.activo, true) = true
  ),
  fuente AS (
    SELECT
      ppd.id AS det_id,
      mc.caso_bib_id,
      mc.nombre_caso
    FROM public.pedido_proveedor_detalle ppd
    JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
    JOIN pe_pp ON pe_pp.pp_id = pp.id
    LEFT JOIN map_linea_caso mc
      ON mc.proveedor_id = pp.proveedor_importacion_id
     AND mc.linea_cod = btrim(ppd.linea)
  ),
  upd AS (
    UPDATE public.pedido_proveedor_detalle ppd
    SET
      descp_caso_snapshot  = f.nombre_caso,
      biblioteca_id        = f.caso_bib_id,
      precio_lpn           = COALESCE(ppd.precio_lpn, ppd.unit_fob_ajustado),
      precio_vinculado_en  = now(),
      precio_vinculado_por = p_usuario_id
    FROM fuente f
    WHERE ppd.id = f.det_id
      AND f.nombre_caso IS NOT NULL
    RETURNING ppd.id,
              UPPER(TRIM(ppd.descp_caso_snapshot)) AS caso_u,
              ppd.precio_lpn AS lpn
  ),
  upd_tiers AS (
    UPDATE public.pedido_proveedor_detalle ppd
    SET
      precio_lpc03 = CASE
        WHEN u.caso_u = 'PROMOCIONAL' THEN u.lpn
        ELSE ROUND(u.lpn * 1.12)
      END,
      precio_lpc04 = CASE
        WHEN u.caso_u = 'PROMOCIONAL' THEN NULL
        ELSE ROUND(u.lpn * 1.20)
      END
    FROM upd u
    WHERE ppd.id = u.id
      AND u.lpn IS NOT NULL
      AND u.lpn > 0
    RETURNING ppd.id
  ),
  stats AS (
    SELECT
      (SELECT COUNT(*) FROM upd) AS n_upd,
      (SELECT COUNT(*) FROM upd WHERE caso_u = 'PROMOCIONAL') AS n_promo,
      (SELECT COUNT(*) FROM fuente WHERE nombre_caso IS NULL) AS n_sin
  )
  SELECT n_upd, n_promo, n_sin
  INTO v_actualizados, v_promo, v_sin_caso
  FROM stats;

  UPDATE public.pedido_proveedor pp
  SET biblioteca_precio_id = p_biblioteca_precio_id
  WHERE pp.id IN (
    SELECT pp2.id
    FROM public.pedido_proveedor pp2
    JOIN public.quincena_arribo qa ON qa.id = pp2.quincena_arribo_id
    WHERE pp2.entidad_comercial = 'STOCK'
      AND pp2.deposito_codigo IS NOT NULL
      AND pp2.estado_transito = 'EN_DEPOSITO'
      AND pp2.categoria_id = 1
      AND lower(trim(qa.descripcion)) = lower('Pronta entrega')
      AND (
        v_batch_norm IS NULL
        OR lower(btrim(pp2.numero_proforma)) = v_batch_norm
      )
  );

  GET DIAGNOSTICS v_pp_locked = ROW_COUNT;

  IF v_batch_norm IS NOT NULL AND v_pp_locked = 0 THEN
    RETURN jsonb_build_object(
      'success', false,
      'error', format('Batch PE «%s» no encontrado en pedido_proveedor STOCK', p_numero_proforma),
      'detail', 'BATCH_SIN_PP'
    );
  END IF;

  RETURN jsonb_build_object(
    'success', true,
    'biblioteca_id', p_biblioteca_precio_id,
    'biblioteca_nombre', v_bib_nombre,
    'actualizados', v_actualizados,
    'promocionales', v_promo,
    'sin_caso_bcl', v_sin_caso,
    'pp_candados', v_pp_locked,
    'numero_proforma', v_batch_norm
  );
END;
$function$;

COMMIT;

SELECT 'MIG-158 OK: vincular_biblioteca_a_pe batch CI' AS estado;
