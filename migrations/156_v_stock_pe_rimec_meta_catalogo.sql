-- MIG-156 · v_stock_pe_rimec: columnas catálogo faltantes (hotfix local)
-- Causa error: column v_stock_pe_rimec.color_tono_canon does not exist
-- + genero_codigo · descp_genero · ramo_tipo · grada
-- NO toca v_stock_rimec (CP). Conserva precios PPD de la vista PE vigente.

DROP VIEW IF EXISTS public.v_stock_pe_rimec CASCADE;

CREATE VIEW public.v_stock_pe_rimec AS
SELECT
  ppd.id AS det_id,
  pp.id AS pp_id,
  pp.numero_registro AS pp_nro,
  COALESCE(pp.numero_proforma, ''::text) AS proforma,
  NULL::text AS eta,
  pp.quincena_arribo_id,
  qa.descripcion AS quincena_desc,
  pp.estado AS pp_estado,
  COALESCE(ppd.id_marca::bigint, l.marca_id, 0::bigint) AS marca_id,
  COALESCE(mv.descp_marca, mv_l.descp_marca, 'RIMEC'::text) AS descp_marca,
  COALESCE(lr.linea_id, l.id, x.cast_linea_id) AS linea_id,
  COALESCE(lr.referencia_id, ref_j.id, x.cast_referencia_id) AS referencia_id,
  COALESCE(lr.grupo_estilo_id, x.cast_style_id) AS grupo_estilo_id,
  lr.tipo_1_id,
  COALESCE(ppd.linea, ''::text) AS linea_codigo,
  COALESCE(ppd.referencia, ''::text) AS referencia_codigo,
  COALESCE(COALESCE(lr.grupo_estilo_id, x.cast_style_id)::text, btrim(COALESCE(ppd.style_code, ''::text)), ''::text) AS style_code,
  COALESCE(ppd.nombre, ''::text) AS nombre,
  COALESCE(ppd.material_code, ''::text) AS material_code,
  COALESCE(ppd.descp_material, ''::text) AS descp_material,
  COALESCE(ppd.color_code, ''::text) AS color_code,
  COALESCE(ppd.descp_color, ''::text) AS descp_color,
  col_j.hex_web AS color_hex,
  ppd.grades_json,
  COALESCE(ppd.cantidad_cajas, 0) AS cantidad_cajas,
  COALESCE(ppd.cantidad_pares, 0) AS cantidad_pares,
  COALESCE(ppd.pares_vendidos, 0) AS pares_vendidos,
  GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) AS saldo_pares,
  CASE
    WHEN GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
    THEN GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0))
    ELSE 0
  END AS pares_por_caja,
  GREATEST(0, ROUND(GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0))))::integer AS cajas_disponibles,
  ppd.unit_fob_ajustado,
  COALESCE(ppd.precio_lpn, ppd.unit_fob_ajustado, 0::numeric) AS lpn,
  ppd.precio_lpc02 AS lpc02,
  ppd.precio_lpc03 AS lpc03,
  ppd.precio_lpc04 AS lpc04,
  ppd.descp_caso_snapshot AS caso_precio,
  ppd.biblioteca_id AS caso_id,
  COALESCE(
    NULLIF(btrim(ppd.descp_caso_snapshot), ''::text),
    'PE · '::text || COALESCE(pp.numero_proforma, ''::text)
  ) AS descp_caso,
  COALESCE(lr.descp_grupo_estilo, ge.descp_grupo_estilo, ''::text) AS descp_grupo_estilo,
  COALESCE(lr.descp_tipo_1, t1.descp_tipo_1, ''::text) AS descp_tipo_1,
  CASE
    WHEN pp.proveedor_importacion_id = 638
     AND NULLIF(btrim(ppd.linea), '') IS NOT NULL
     AND NULLIF(
       regexp_replace(COALESCE(pe_img.excel_color_code, col_j.nombre, ''), '^[Kk]', ''),
       ''
     ) IS NOT NULL
    THEN 'https://extrlcvcgypwazxipvqm.supabase.co/storage/v1/object/public/productos/'
         || btrim(ppd.linea) || '_'
         || regexp_replace(COALESCE(pe_img.excel_color_code, col_j.nombre), '^[Kk]', '') || '.jpg'
    WHEN COALESCE(ppd.linea, ''::text) <> ''
     AND COALESCE(ppd.referencia, ''::text) <> ''
     AND COALESCE(ppd.material_code, ''::text) <> ''
     AND COALESCE(ppd.color_code, ''::text) <> ''
    THEN 'https://extrlcvcgypwazxipvqm.supabase.co/storage/v1/object/public/productos/'
         || ppd.linea || '-' || ppd.referencia || '-' || ppd.material_code || '-' || ppd.color_code || '.jpg'
    ELSE NULL::text
  END AS imagen_url,
  'PRONTA_ENTREGA'::text AS origen_tipo,
  NULL::bigint AS deposito_id,
  NULL::bigint AS clasificacion_stock_id,
  pp.deposito_codigo AS deposito_nombre,
  NULL::text AS clasificacion_stock_descp,
  pp.proveedor_importacion_id,
  CASE pp.proveedor_importacion_id
    WHEN 654 THEN 1
    WHEN 638 THEN 2
    ELSE NULL::integer
  END AS tipo_v2_id,
  NULLIF(
    regexp_replace(COALESCE(pe_img.excel_color_code, col_j.nombre, ''), '^[Kk]', ''),
    ''
  ) AS imagen_color_excel,
  NULLIF(btrim(ppd.grada), ''::text) AS grada,
  col_j.tono_canon AS color_tono_canon,
  l.genero_id,
  gen.codigo AS genero_codigo,
  gen.descripcion AS descp_genero,
  CASE
    WHEN pp.proveedor_importacion_id = 638 THEN 'CONFECCIONES'::text
    ELSE 'CALZADO'::text
  END AS ramo_tipo
FROM pedido_proveedor_detalle ppd
JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
JOIN quincena_arribo qa ON qa.id = pp.quincena_arribo_id
CROSS JOIN LATERAL (
  SELECT
    CASE WHEN NULLIF(btrim(ppd.linea), '') ~ '^[0-9]+$' THEN btrim(ppd.linea)::bigint ELSE NULL::bigint END AS cast_linea_id,
    CASE WHEN NULLIF(btrim(ppd.referencia), '') ~ '^[0-9]+$' THEN btrim(ppd.referencia)::bigint ELSE NULL::bigint END AS cast_referencia_id,
    CASE WHEN NULLIF(btrim(ppd.material_code), '') ~ '^[0-9]+$' THEN btrim(ppd.material_code)::bigint ELSE NULL::bigint END AS cast_material_id,
    CASE WHEN NULLIF(btrim(ppd.color_code), '') ~ '^[0-9]+$' THEN btrim(ppd.color_code)::bigint ELSE NULL::bigint END AS cast_color_id,
    CASE WHEN NULLIF(btrim(ppd.style_code), '') ~ '^[0-9]+$' THEN btrim(ppd.style_code)::bigint ELSE NULL::bigint END AS cast_style_id
) x
LEFT JOIN LATERAL (
  SELECT NULLIF(btrim(s.excel_color_code), '') AS excel_color_code
  FROM stock_pe_staging_migrated m
  JOIN stock_pronta_entrega_rimec s ON s.id = m.staging_id
  WHERE m.ppd_id = ppd.id
  ORDER BY s.id
  LIMIT 1
) pe_img ON TRUE
LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
LEFT JOIN linea l
  ON l.proveedor_id = pp.proveedor_importacion_id
 AND l.codigo_proveedor = x.cast_linea_id
LEFT JOIN genero gen ON gen.id = l.genero_id
LEFT JOIN marca_v2 mv_l ON mv_l.id_marca = l.marca_id
LEFT JOIN material m
  ON m.proveedor_id = pp.proveedor_importacion_id
 AND m.codigo_proveedor = x.cast_material_id
LEFT JOIN color col_j
  ON col_j.proveedor_id = pp.proveedor_importacion_id
 AND col_j.codigo_proveedor = x.cast_color_id
 AND col_j.activo = true
LEFT JOIN referencia ref_j
  ON ref_j.linea_id = l.id
 AND ref_j.codigo_proveedor = x.cast_referencia_id
LEFT JOIN linea_referencia lr
  ON lr.linea_id = l.id
 AND lr.referencia_id = ref_j.id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = COALESCE(lr.grupo_estilo_id, x.cast_style_id)
LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
WHERE pp.entidad_comercial = 'STOCK'
  AND pp.deposito_codigo IS NOT NULL
  AND pp.estado_transito = 'EN_DEPOSITO'
  AND pp.categoria_id = 1
  AND pp.quincena_arribo_id = 25
  AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0;

COMMENT ON VIEW public.v_stock_pe_rimec IS
  'Pronta entrega RIMEC · PPD · MIG-156 tono+genero+ramo+grada (hotfix catálogo)';
