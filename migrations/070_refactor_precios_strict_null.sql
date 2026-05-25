-- MIG-070: REFACTORIZACIÓN TRANSACCIONAL DE PRECIOS - Criterio Estricto NULL
-- Autor: Claude Code bajo directiva de Héctor Segovia
-- Fecha: 2026-05-21
-- Objetivo: Desacoplar caso_precio_biblioteca de v_stock_rimec y aplicar Opción A (Strict NULL)
-- Filosofía: "El sistema no debe enmascarar omisiones operativas"

-- ============================================================================
-- ELIMINACIÓN DE REGLAS DIFUSAS - Saneamiento de Vista
-- ============================================================================

-- Eliminar vista actual (que contiene JOIN a caso_precio_biblioteca de MIG-067)
DROP VIEW IF EXISTS public.v_stock_rimec CASCADE;

-- Recrear vista con MAPEO DIRECTO OBLIGATORIO a precio_lista únicamente
CREATE OR REPLACE VIEW public.v_stock_rimec AS
SELECT DISTINCT ON (ppd.id)
  ppd.id AS det_id,
  pp.id AS pp_id,
  pp.numero_registro AS pp_nro,
  COALESCE(pp.numero_proforma, '') AS proforma,
  pp.fecha_arribo_estimada::text AS eta,
  pp.estado AS pp_estado,
  ppd.id_marca::bigint AS marca_id,
  COALESCE(mv.descp_marca, '?') AS descp_marca,
  COALESCE(lr.linea_id, l.id, x.cast_linea_id) AS linea_id,
  COALESCE(lr.referencia_id, ref_j.id, x.cast_referencia_id) AS referencia_id,
  COALESCE(lr.grupo_estilo_id, x.cast_style_id) AS grupo_estilo_id,
  lr.tipo_1_id,
  COALESCE(ppd.linea, '') AS linea_codigo,
  COALESCE(ppd.referencia, '') AS referencia_codigo,
  COALESCE(COALESCE(lr.grupo_estilo_id, x.cast_style_id)::text, btrim(COALESCE(ppd.style_code, '')), '') AS style_code,
  COALESCE(ppd.nombre, '') AS nombre,
  COALESCE(ppd.material_code, '') AS material_code,
  COALESCE(ppd.descp_material, '') AS descp_material,
  COALESCE(ppd.color_code, '') AS color_code,
  COALESCE(ppd.descp_color, '') AS descp_color,
  col_j.hex_web AS color_hex,
  ppd.grades_json,
  COALESCE(ppd.cantidad_cajas, 0) AS cantidad_cajas,
  COALESCE(ppd.cantidad_pares, 0) AS cantidad_pares,
  COALESCE(ppd.pares_vendidos, 0) AS pares_vendidos,
  GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) AS saldo_pares,
  CASE
    WHEN COALESCE(ppd.cantidad_cajas, 0) > 0 THEN ppd.cantidad_pares / ppd.cantidad_cajas
    ELSE 0
  END AS pares_por_caja,
  GREATEST(0, COALESCE(ppd.cantidad_cajas, 0) -
    CASE
      WHEN COALESCE(ppd.cantidad_cajas, 0) > 0 AND COALESCE(ppd.cantidad_pares, 0) > 0
        THEN (COALESCE(ppd.pares_vendidos, 0) + ppd.cantidad_pares / ppd.cantidad_cajas - 1) / (ppd.cantidad_pares / ppd.cantidad_cajas)
      ELSE COALESCE(ppd.pares_vendidos, 0)
    END) AS cajas_disponibles,
  ppd.unit_fob_ajustado,
  -- ═══════════════════════════════════════════════════════════════════════
  -- MIG-070: MAPEO DIRECTO OBLIGATORIO - Precios y Caso SOLO desde precio_lista
  -- ═══════════════════════════════════════════════════════════════════════
  -- Si precio_lista existe → usar valores
  -- Si NO existe (PP sin evento) → NULL (NO fallback a caso_precio_biblioteca)
  pl.lpn,
  pl.lpc02,
  pl.lpc03,
  pl.lpc04,
  pl.nombre_caso_aplicado AS caso_precio,
  pl.caso_id,
  -- OPCIÓN A (Criterio Estricto): Sin fallback - NULL si no hay evento
  pl.nombre_caso_aplicado AS descp_caso,
  -- ═══════════════════════════════════════════════════════════════════════
  COALESCE(lr.descp_grupo_estilo, ge.descp_grupo_estilo, '') AS descp_grupo_estilo,
  COALESCE(lr.descp_tipo_1, t1.descp_tipo_1, '') AS descp_tipo_1,
  CASE
    WHEN COALESCE(ppd.linea, '') <> ''
      AND COALESCE(ppd.referencia, '') <> ''
      AND COALESCE(ppd.material_code, '') <> ''
      AND COALESCE(ppd.color_code, '') <> ''
    THEN 'https://extrlcvcgypwazxipvqm.supabase.co/storage/v1/object/public/productos/'
         || ppd.linea || '-' || ppd.referencia || '-' || ppd.material_code || '-' || ppd.color_code || '.jpg'
    ELSE NULL
  END AS imagen_url,
  'TRÁNSITO_PP' AS origen_tipo,
  NULL::bigint AS deposito_id,
  NULL::bigint AS clasificacion_stock_id,
  NULL::text AS deposito_nombre,
  NULL::text AS clasificacion_stock_descp
FROM pedido_proveedor_detalle ppd
JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
LEFT JOIN material m ON m.codigo_proveedor::text = ppd.material_code AND m.proveedor_id = pp.proveedor_importacion_id
LEFT JOIN linea l ON l.codigo_proveedor::text = ppd.linea AND l.proveedor_id = pp.proveedor_importacion_id
LEFT JOIN color col_j ON col_j.codigo_proveedor::text = ppd.color_code
  AND col_j.proveedor_id = pp.proveedor_importacion_id
  AND col_j.activo = true
LEFT JOIN referencia ref_j ON ref_j.codigo_proveedor::text = ppd.referencia AND ref_j.linea_id = l.id
CROSS JOIN LATERAL (
  SELECT
    CASE WHEN NULLIF(btrim(ppd.linea), '') ~ '^[0-9]+$' THEN btrim(ppd.linea)::bigint ELSE NULL END AS cast_linea_id,
    CASE WHEN NULLIF(btrim(ppd.referencia), '') ~ '^[0-9]+$' THEN btrim(ppd.referencia)::bigint ELSE NULL END AS cast_referencia_id,
    CASE WHEN NULLIF(btrim(ppd.style_code), '') ~ '^[0-9]+$' THEN btrim(ppd.style_code)::bigint ELSE NULL END AS cast_style_id
) x
LEFT JOIN linea_referencia lr ON lr.linea_id = l.id AND lr.referencia_id = ref_j.id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = COALESCE(lr.grupo_estilo_id, x.cast_style_id)
LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
-- ═══════════════════════════════════════════════════════════════════════
-- MIG-070: JOIN ÚNICO a precio_lista - Sin fallback a caso_precio_biblioteca
-- Si ic.precio_evento_id es NULL → pl será NULL → precios y caso en NULL
-- ═══════════════════════════════════════════════════════════════════════
LEFT JOIN LATERAL (
  SELECT pl2.lpn, pl2.lpc02, pl2.lpc03, pl2.lpc04, pl2.nombre_caso_aplicado, pl2.caso_id
  FROM precio_lista pl2
  WHERE pl2.evento_id = ic.precio_evento_id
    AND pl2.linea_id = COALESCE(l.id, ref_j.linea_id)
    AND pl2.referencia_id = ref_j.id
    AND pl2.material_id = m.id
  LIMIT 1
) pl ON true
-- ═══════════════════════════════════════════════════════════════════════
-- NOTA: caso_precio_biblioteca NO participa en el catálogo web
-- Tabla caso_precio_biblioteca se mantiene intacta como base de configuración
-- para Streamlit (generación de eventos de precio) pero NO para consulta web
-- ═══════════════════════════════════════════════════════════════════════
WHERE (pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO']))
  AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
ORDER BY ppd.id;

-- ============================================================================
-- Comentario de auditoría
-- ============================================================================
COMMENT ON VIEW public.v_stock_rimec IS
  'MIG-070: Vista refactorizada con criterio estricto NULL. '
  'Desacoplado caso_precio_biblioteca. Precios y caso SOLO desde precio_lista. '
  'Si PP sin evento → caso=NULL (expone omisiones operativas). '
  'Fecha: 2026-05-21';

-- ============================================================================
-- NOTA DE GOBERNANZA
-- ============================================================================
-- La tabla caso_precio_biblioteca permanece en la base de datos para:
-- 1. Configuración de eventos de precio en Streamlit (control_central)
-- 2. Referencia histórica y auditoría
-- 3. Base de cálculo para generación de eventos futuros
--
-- Pero NO participa en:
-- - Renderizado del catálogo web (rimec-web)
-- - Cálculo transaccional de precios en carrito
-- - Inserción de caso_id en factura_interna
--
-- TRAZABILIDAD: El flujo es:
-- 1. Streamlit genera precio_lista desde caso_precio_biblioteca
-- 2. Catálogo web lee precio_lista (no caso_precio_biblioteca)
-- 3. Frontend envía caso_id exacto visto por vendedor
-- 4. RPC confirmar_pedido_web hereda caso_id del payload
-- 5. factura_interna registra caso_id sin recálculo
