-- MIG-153 — Vincular biblioteca → casos PE (etiqueta PROMO en RIMEC Web)
-- Director 2026-07-15 · NO listado precio · solo BCL → descp_caso_snapshot en PPD
--
-- Botón panel Stock Pronta Entrega: elige biblioteca → persiste caso por línea.
-- Re-vincular otra biblioteca → actualiza etiquetas (PROMOCIONAL, etc.).

BEGIN;

ALTER TABLE public.pedido_proveedor
  ADD COLUMN IF NOT EXISTS biblioteca_precio_id bigint NULL
    REFERENCES public.biblioteca_precio(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.pedido_proveedor.biblioteca_precio_id IS
  'MIG-153: biblioteca BCL vinculada al universo PE (STOCK). Candado etiquetas caso.';

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
        p_numero_proforma IS NULL
        OR btrim(p_numero_proforma) = ''
        OR pp.numero_proforma = p_numero_proforma
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
        p_numero_proforma IS NULL
        OR btrim(p_numero_proforma) = ''
        OR pp2.numero_proforma = p_numero_proforma
      )
  );

  RETURN jsonb_build_object(
    'success', true,
    'biblioteca_id', p_biblioteca_precio_id,
    'biblioteca_nombre', v_bib_nombre,
    'actualizados', v_actualizados,
    'promocionales', v_promo,
    'sin_caso_bcl', v_sin_caso,
    'numero_proforma', p_numero_proforma
  );
END;
$function$;

COMMENT ON FUNCTION public.vincular_biblioteca_a_pe(bigint, bigint, text) IS
  'PE STOCK: vincula biblioteca BCL → descp_caso_snapshot PPD (PROMO Web). Re-vincular actualiza.';

COMMIT;

SELECT 'MIG-153 OK: vincular_biblioteca_a_pe' AS estado;
