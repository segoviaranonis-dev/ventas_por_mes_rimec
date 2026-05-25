-- OT-009: Pegar en Supabase SQL Editor (solo lectura). Guardar resultados para evidencia.
-- Fecha: 2026-05-22

-- A) Cobertura global (debe coincidir con OT-004)
SELECT
  COUNT(*) AS total_skus,
  COUNT(*) FILTER (WHERE lpn IS NOT NULL) AS con_lpn,
  COUNT(*) FILTER (WHERE cajas_disponibles > 0) AS con_stock
FROM public.v_stock_rimec;

-- B) ¿precio_lista tiene filas para eventos de PPs abiertos?
SELECT pl.evento_id, COUNT(*) AS filas, COUNT(*) FILTER (WHERE lpn > 0) AS con_lpn_positivo
FROM public.precio_lista pl
WHERE pl.evento_id IN (
  SELECT DISTINCT icp.precio_evento_id
  FROM public.intencion_compra_pedido icp
  JOIN public.pedido_proveedor pp ON pp.id = icp.pedido_proveedor_id
  WHERE pp.estado IN ('ABIERTO', 'ENVIADO') AND icp.precio_evento_id IS NOT NULL
)
GROUP BY pl.evento_id
ORDER BY pl.evento_id;

-- C) 3 SKUs muestra
SELECT det_id, pp_id, pp_nro, descp_marca, linea_codigo, referencia_codigo, material_code, lpn, caso_id
FROM public.v_stock_rimec
WHERE cajas_disponibles > 0
ORDER BY descp_marca, linea_codigo
LIMIT 3;

-- D+E) Rastreo automático del primer SKU con stock (sin variables)
WITH muestra AS (
  SELECT det_id, pp_id
  FROM public.v_stock_rimec
  WHERE cajas_disponibles > 0
  ORDER BY descp_marca, linea_codigo
  LIMIT 1
),
ev AS (
  SELECT m.det_id, m.pp_id, icp2.precio_evento_id
  FROM muestra m
  JOIN public.pedido_proveedor_detalle ppd ON ppd.id = m.det_id
  JOIN public.intencion_compra_pedido icp2 ON icp2.pedido_proveedor_id = m.pp_id
  JOIN public.intencion_compra ic2 ON ic2.id = icp2.intencion_compra_id
  WHERE icp2.precio_evento_id IS NOT NULL
    AND (ppd.id_marca IS NULL OR ic2.id_marca = ppd.id_marca::bigint)
  ORDER BY CASE WHEN ppd.id_marca IS NOT NULL AND ic2.id_marca = ppd.id_marca::bigint THEN 0 ELSE 1 END, icp2.id
  LIMIT 1
),
ids AS (
  SELECT m.det_id, m.pp_id,
         ppd.linea AS cod_linea_pp, l.id AS linea_id,
         ppd.referencia AS cod_ref_pp, r.id AS referencia_id,
         ppd.material_code AS cod_mat_pp, mtab.id AS material_id
  FROM muestra m
  JOIN public.pedido_proveedor_detalle ppd ON ppd.id = m.det_id
  JOIN public.pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
  LEFT JOIN public.linea l ON l.codigo_proveedor::text = ppd.linea AND l.proveedor_id = pp.proveedor_importacion_id
  LEFT JOIN public.referencia r ON r.codigo_proveedor::text = ppd.referencia AND r.linea_id = l.id
  LEFT JOIN public.material mtab ON mtab.codigo_proveedor::text = ppd.material_code AND mtab.proveedor_id = pp.proveedor_importacion_id
)
SELECT i.det_id, i.pp_id, e.precio_evento_id,
       i.cod_linea_pp, i.linea_id, i.cod_ref_pp, i.referencia_id, i.cod_mat_pp, i.material_id,
       (SELECT COUNT(*) FROM public.precio_lista pl
        WHERE pl.evento_id = e.precio_evento_id
          AND pl.linea_id = i.linea_id AND pl.referencia_id = i.referencia_id AND pl.material_id = i.material_id) AS match_triplete,
       (SELECT COUNT(*) FROM public.precio_lista pl
        WHERE pl.evento_id = e.precio_evento_id
          AND pl.linea_id = i.linea_id AND pl.referencia_id = i.referencia_id) AS match_sin_material,
       (SELECT COUNT(*) FROM public.precio_lista pl
        WHERE pl.linea_id = i.linea_id AND pl.referencia_id = i.referencia_id) AS match_cualquier_evento
FROM ids i
LEFT JOIN ev e ON e.det_id = i.det_id;
