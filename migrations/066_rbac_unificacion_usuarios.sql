-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 066: Unificación de Usuarios y Control de Acceso Corporativo (RBAC)
--
-- 1. Crea las tablas maestras public.maestro_rol_acceso y public.modulo_sistema.
-- 2. Vincula usuario_v2 a maestro_rol_acceso.
-- 3. Deprecia y desvincula la tabla vendedor_v2 (se renombra a vendedor_v2_deprecated).
-- 4. Vincula tablas activas (pedidos, facturas, intenciones, marcas) a usuario_v2.
-- 5. Agrega una restricción CHECK en pedido_venta_rimec, factura_interna e
--    intencion_compra para validar que el vendedor sea un usuario con rol
--    'VENDEDOR' o 'ADMIN'.
-- 6. Refactoriza v_stock_rimec para resolver caso_id y descp_caso desde precio_lista.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. Eliminar la vista v_stock_rimec antes de realizar cambios de esquema ──
DROP VIEW IF EXISTS public.v_stock_rimec CASCADE;

-- ── 2. Crear tabla maestro_rol_acceso ──
CREATE TABLE IF NOT EXISTS public.maestro_rol_acceso (
    id int2 PRIMARY KEY,
    nombre_rol text UNIQUE NOT NULL,
    descripcion text
);

-- Poblar roles estándar
INSERT INTO public.maestro_rol_acceso (id, nombre_rol, descripcion) VALUES
(1, 'ADMIN', 'Administrador General del Sistema'),
(2, 'SUPERVISOR', 'Supervisor Operativo/Comercial'),
(3, 'VENDEDOR', 'Vendedor de Ventas Mayoristas'),
(4, 'OPERARIO', 'Operario de Depósito/Logística')
ON CONFLICT (id) DO UPDATE SET
  nombre_rol = EXCLUDED.nombre_rol,
  descripcion = EXCLUDED.descripcion;

-- ── 3. Crear tabla modulo_sistema ──
CREATE TABLE IF NOT EXISTS public.modulo_sistema (
    id int2 PRIMARY KEY,
    codigo_modulo text UNIQUE NOT NULL
);

-- Poblar módulos
INSERT INTO public.modulo_sistema (id, codigo_modulo) VALUES
(1, 'NEXUS_STREAMLIT'),
(2, 'REPORT_SALES'),
(3, 'REPORT_RETAIL'),
(4, 'RIMEC_WEB_VENTAS')
ON CONFLICT (id) DO UPDATE SET
  codigo_modulo = EXCLUDED.codigo_modulo;

-- ── 4. Modificar usuario_v2 y vincular a maestro_rol_acceso ──
ALTER TABLE public.usuario_v2 ADD COLUMN IF NOT EXISTS rol_id int2 REFERENCES public.maestro_rol_acceso(id);

-- Backfill de roles basado en la columna categoria
UPDATE public.usuario_v2
SET rol_id = CASE
    WHEN UPPER(TRIM(categoria)) IN ('ADMIN', 'SU') THEN 1
    WHEN UPPER(TRIM(categoria)) = 'SUPERVISOR' THEN 2
    WHEN UPPER(TRIM(categoria)) = 'VENDEDOR' THEN 3
    WHEN UPPER(TRIM(categoria)) = 'OPERARIO' THEN 4
    ELSE 3 -- fallback a VENDEDOR
END
WHERE rol_id IS NULL;

-- ── 5. Desvincular y depreciar vendedor_v2 ──

-- Eliminar FKs desde registro_ventas_general_v2 (tabla histórica gigante)
ALTER TABLE public.registro_ventas_general_v2 DROP CONSTRAINT IF EXISTS fk_ventas_vendedor;
ALTER TABLE public.registro_ventas_general_v2 DROP CONSTRAINT IF EXISTS fk_v2_ventas_vendedor;

-- Eliminar FKs desde vendedor_marca_v2
ALTER TABLE public.vendedor_marca_v2 DROP CONSTRAINT IF EXISTS vendedor_marca_v2_id_vendedor_fkey;
ALTER TABLE public.vendedor_marca_v2 DROP CONSTRAINT IF EXISTS fk_v2_vm_vendedor;

-- Eliminar FK desde intencion_compra
ALTER TABLE public.intencion_compra DROP CONSTRAINT IF EXISTS intencion_compra_id_vendedor_fkey;

-- Eliminar FK desde factura_interna
ALTER TABLE public.factura_interna DROP CONSTRAINT IF EXISTS factura_interna_vendedor_id_fkey;

-- Eliminar FK desde pedido_venta_rimec
ALTER TABLE public.pedido_venta_rimec DROP CONSTRAINT IF EXISTS pedido_venta_rimec_vendedor_id_fkey;

-- Renombrar vendedor_v2 a vendedor_v2_deprecated
DO $$
BEGIN
  IF EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'vendedor_v2') THEN
    ALTER TABLE public.vendedor_v2 RENAME TO vendedor_v2_deprecated;
  END IF;
END $$;

-- ── 6. Vincular tablas activas a usuario_v2 ──

ALTER TABLE public.pedido_venta_rimec 
  ADD CONSTRAINT fk_pedido_venta_vendedor FOREIGN KEY (vendedor_id) REFERENCES public.usuario_v2(id_usuario);

ALTER TABLE public.factura_interna 
  ADD CONSTRAINT fk_factura_interna_vendedor FOREIGN KEY (vendedor_id) REFERENCES public.usuario_v2(id_usuario);

ALTER TABLE public.intencion_compra 
  ADD CONSTRAINT fk_intencion_compra_vendedor FOREIGN KEY (id_vendedor) REFERENCES public.usuario_v2(id_usuario);

ALTER TABLE public.vendedor_marca_v2 
  ADD CONSTRAINT fk_vendedor_marca_vendedor FOREIGN KEY (id_vendedor) REFERENCES public.usuario_v2(id_usuario);

-- ── 7. Implementar Check Constraints de Gobernanza de Roles ──

CREATE OR REPLACE FUNCTION public.fn_es_usuario_vendedor_o_admin(usr_id BIGINT)
RETURNS BOOLEAN AS $$
DECLARE
  v_role TEXT;
BEGIN
  IF usr_id IS NULL THEN
    RETURN TRUE;
  END IF;
  
  SELECT r.nombre_rol INTO v_role
  FROM public.usuario_v2 u
  JOIN public.maestro_rol_acceso r ON u.rol_id = r.id
  WHERE u.id_usuario = usr_id;
  
  RETURN v_role IN ('VENDEDOR', 'ADMIN');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER TABLE public.pedido_venta_rimec 
  ADD CONSTRAINT chk_vendedor_rol CHECK (vendedor_id IS NULL OR fn_es_usuario_vendedor_o_admin(vendedor_id));

ALTER TABLE public.factura_interna 
  ADD CONSTRAINT chk_vendedor_rol CHECK (vendedor_id IS NULL OR fn_es_usuario_vendedor_o_admin(vendedor_id));

ALTER TABLE public.intencion_compra 
  ADD CONSTRAINT chk_vendedor_rol CHECK (id_vendedor IS NULL OR fn_es_usuario_vendedor_o_admin(id_vendedor));

-- ── 8. Re-crear v_stock_rimec refactorizada sin dependencias obsoletas ──

CREATE VIEW public.v_stock_rimec AS
SELECT DISTINCT ON (ppd.id)
    ppd.id AS det_id,
    pp.id AS pp_id,
    pp.numero_registro AS pp_nro,
    COALESCE(pp.numero_proforma, '') AS proforma,
    (pp.fecha_arribo_estimada)::text AS eta,
    pp.estado AS pp_estado,
    ppd.id_marca::bigint AS marca_id,
    COALESCE(mv.descp_marca, '—') AS descp_marca,
    COALESCE(lr.linea_id, l.id, x.cast_linea_id)::bigint AS linea_id,
    COALESCE(lr.referencia_id, ref_j.id, x.cast_referencia_id)::bigint AS referencia_id,
    COALESCE(lr.grupo_estilo_id, x.cast_style_id)::bigint AS grupo_estilo_id,
    lr.tipo_1_id::bigint AS tipo_1_id,
    COALESCE(ppd.linea, '') AS linea_codigo,
    COALESCE(ppd.referencia, '') AS referencia_codigo,
    COALESCE(
        (COALESCE(lr.grupo_estilo_id, x.cast_style_id))::text,
        btrim(COALESCE(ppd.style_code::text, '')),
        ''
    ) AS style_code,
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
    GREATEST(
        0,
        COALESCE(ppd.cantidad_cajas, 0) - CASE
            WHEN COALESCE(ppd.cantidad_cajas, 0) > 0
             AND COALESCE(ppd.cantidad_pares, 0) > 0
            THEN (
                COALESCE(ppd.pares_vendidos, 0)
                + (ppd.cantidad_pares / ppd.cantidad_cajas)
                - 1
            ) / (ppd.cantidad_pares / ppd.cantidad_cajas)
            ELSE COALESCE(ppd.pares_vendidos, 0)
        END
    )::integer AS cajas_disponibles,
    ppd.unit_fob_ajustado,
    pl.lpn,
    pl.lpc02,
    pl.lpc03,
    pl.lpc04,
    pl.nombre_caso_aplicado AS caso_precio,
    pl.caso_id AS caso_id,
    COALESCE(pl.nombre_caso_aplicado, '') AS descp_caso,
    COALESCE(lr.descp_grupo_estilo, ge.descp_grupo_estilo, '') AS descp_grupo_estilo,
    COALESCE(lr.descp_tipo_1, t1.descp_tipo_1, '') AS descp_tipo_1,
    CASE
        WHEN COALESCE(ppd.linea, '') <> ''
         AND COALESCE(ppd.referencia, '') <> ''
         AND COALESCE(ppd.material_code, '') <> ''
         AND COALESCE(ppd.color_code, '') <> ''
        THEN 'https://extrlcvcgypwazxipvqm.supabase.co/storage/v1/object/public/productos/'
             || ppd.linea || '-' || ppd.referencia || '-'
             || ppd.material_code || '-' || ppd.color_code || '.jpg'
         ELSE NULL
    END AS imagen_url,
    'TRÁNSITO_PP'::text AS origen_tipo,
    NULL::bigint AS deposito_id,
    NULL::bigint AS clasificacion_stock_id,
    NULL::text AS deposito_nombre,
    NULL::text AS clasificacion_stock_descp
FROM pedido_proveedor_detalle ppd
JOIN pedido_proveedor pp ON pp.id = ppd.pedido_proveedor_id
LEFT JOIN marca_v2 mv ON mv.id_marca = ppd.id_marca
LEFT JOIN intencion_compra ic ON ic.id = pp.id_intencion_compra
LEFT JOIN material m
    ON m.codigo_proveedor::text = ppd.material_code
   AND m.proveedor_id = pp.proveedor_importacion_id
LEFT JOIN linea l
    ON l.codigo_proveedor::text = ppd.linea
   AND l.proveedor_id = pp.proveedor_importacion_id
LEFT JOIN color col_j
    ON col_j.codigo_proveedor::text = ppd.color_code
   AND col_j.proveedor_id = pp.proveedor_importacion_id
   AND col_j.activo = TRUE
LEFT JOIN referencia ref_j
    ON ref_j.codigo_proveedor::text = ppd.referencia
    AND ref_j.linea_id = l.id
CROSS JOIN LATERAL (
    SELECT
        CASE WHEN nullif(btrim(ppd.linea::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.linea::text)::bigint ELSE NULL::bigint END AS cast_linea_id,
        CASE WHEN nullif(btrim(ppd.referencia::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.referencia::text)::bigint ELSE NULL::bigint END AS cast_referencia_id,
        CASE WHEN nullif(btrim(ppd.style_code::text), '') ~ '^[0-9]+$'
            THEN btrim(ppd.style_code::text)::bigint ELSE NULL::bigint END AS cast_style_id
) x
LEFT JOIN linea_referencia lr
    ON lr.linea_id = l.id AND lr.referencia_id = ref_j.id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = COALESCE(lr.grupo_estilo_id, x.cast_style_id)
LEFT JOIN tipo_1 t1 ON t1.id_tipo_1 = lr.tipo_1_id
LEFT JOIN LATERAL (
    SELECT pl2.lpn, pl2.lpc02, pl2.lpc03, pl2.lpc04, pl2.nombre_caso_aplicado, pl2.caso_id
    FROM precio_lista pl2
    WHERE pl2.evento_id = COALESCE(ic.precio_evento_id, (
        SELECT pl3.evento_id
        FROM precio_lista pl3
        JOIN precio_evento pe3 ON pe3.id = pl3.evento_id
        WHERE pe3.estado = 'cerrado'
          AND pl3.linea_id = COALESCE(l.id, ref_j.linea_id)
          AND pl3.referencia_id = ref_j.id
          AND pl3.material_id = m.id
        ORDER BY pe3.created_at DESC
        LIMIT 1
    ))
    AND pl2.linea_id = COALESCE(l.id, ref_j.linea_id)
    AND pl2.referencia_id = ref_j.id
    AND pl2.material_id = m.id
    LIMIT 1
) pl ON true
WHERE pp.estado = ANY (ARRAY['ABIERTO', 'ENVIADO'])
  AND GREATEST(0, COALESCE(ppd.cantidad_pares, 0) - COALESCE(ppd.pares_vendidos, 0)) > 0
ORDER BY ppd.id;

COMMENT ON VIEW public.v_stock_rimec IS
  'Catálogo web: tránsito PP en ABIERTO/ENVIADO con saldo. Refactorizado con RBAC y caso desde precio_lista (066).';

COMMIT;
