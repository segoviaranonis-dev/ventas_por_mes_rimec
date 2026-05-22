-- MIG-075 — Backfill inicial snapshot en PPD (PPs ABIERTO/ENVIADO con saldo)
-- Cruza intencion_compra_pedido por marca + precio_lista (staging Alfredo).
-- No sobrescribe filas que ya tienen precio_lpn (re-vincular manual en Streamlit).

BEGIN;

WITH pp_activos AS (
  SELECT DISTINCT pp.id AS pp_id
  FROM public.pedido_proveedor pp
  WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
),
fuente AS (
  SELECT
    ppd.id AS det_id,
    pl.lpn,
    pl.lpc02,
    pl.lpc03,
    pl.lpc04,
    pl.dolar_aplicado,
    (SELECT cpb.id FROM public.caso_precio_biblioteca cpb WHERE cpb.nombre_caso = pl.nombre_caso_aplicado LIMIT 1) AS caso_bib_id,
    pl.nombre_caso_aplicado,
    public.fn_resolver_evento_precio_ppd(pp.id, ppd.id) AS evento_resuelto
  FROM public.pedido_proveedor_detalle ppd
  JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
  JOIN pp_activos pa ON pa.pp_id = pp.id
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
  WHERE GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
    AND ppd.precio_lpn IS NULL
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
    precio_vinculado_en  = COALESCE(ppd.precio_vinculado_en, now()),
    precio_vinculado_por = COALESCE(ppd.precio_vinculado_por, NULL)
  FROM fuente f
  WHERE ppd.id = f.det_id
    AND f.lpn IS NOT NULL
    AND f.evento_resuelto IS NOT NULL
  RETURNING ppd.id
)
SELECT COUNT(*) AS filas_backfill FROM upd;

DO $$
DECLARE
  v_total_saldo bigint;
  v_con_lpn_ppd bigint;
  v_con_lpn_vista bigint;
  v_pl_evento bigint;
BEGIN
  SELECT COUNT(*)
  INTO v_total_saldo
  FROM public.pedido_proveedor_detalle ppd
  JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
  WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
    AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0;

  SELECT COUNT(*)
  INTO v_con_lpn_ppd
  FROM public.pedido_proveedor_detalle ppd
  JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
  WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
    AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
    AND ppd.precio_lpn IS NOT NULL;

  SELECT COUNT(DISTINCT pl.id)
  INTO v_pl_evento
  FROM public.precio_lista pl
  WHERE pl.evento_id IN (
    SELECT DISTINCT icp.precio_evento_id
    FROM public.intencion_compra_pedido icp
    JOIN public.pedido_proveedor pp ON pp.id = icp.pedido_proveedor_id
    WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
      AND icp.precio_evento_id IS NOT NULL
  )
  AND pl.lpn IS NOT NULL;

  RAISE NOTICE 'MIG-075 verificación: SKUs con saldo=% | PPD con precio_lpn=% | filas precio_lista en eventos activos=%',
    v_total_saldo, v_con_lpn_ppd, v_pl_evento;
END $$;

COMMIT;

SELECT 'MIG-075 OK: backfill snapshot PPD' AS estado;
