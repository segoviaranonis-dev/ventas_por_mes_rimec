-- ═══════════════════════════════════════════════════════════════════════════
-- 023 — Reset operativo para iniciar simulación de demo desde cero
--
-- Borra todo el flujo operativo y reinicia IDs a 1. Conserva los "pilares":
--   · Productos: linea, referencia, linea_referencia
--   · Maestras: marca_v2, genero, grupo_estilo_v2, tipo_1, material, color, talla,
--               almacen, proveedor_importacion
--   · Precios (reglas): caso_precio_biblioteca, caso_precio_biblioteca_linea,
--                       listado_precio, listado_de_precio_v2, lista_precio,
--                       precio_evento, precio_evento_caso,
--                       precio_evento_linea_excepcion
--   · Comerciales: cliente_v2, vendedor_v2, plazo_v2
--
-- Borra en una sola sentencia TRUNCATE (atómica). Se omiten las tablas que no
-- existan en esta BD para que la migración sea idempotente entre entornos.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

DO $$
DECLARE
    -- Orden no importa: TRUNCATE multi-tabla acepta FK si todas las tablas
    -- referenciadas (entre sí) están en la lista.
    candidatas text[] := ARRAY[
        -- Catálogo derivado (rehidratable desde traspasos/proformas)
        'combinacion',

        -- Precios (renglones; las reglas se preservan)
        'precio_lista',
        'precio_auditoria',
        'precio',
        'linea_caso',

        -- Web (pedidos online)
        'pedido_web_detalle',
        'pedido_web',

        -- Stock físico (movimientos y traspasos)
        'movimiento_detalle',
        'movimiento',
        'traspaso_detalle',
        'traspaso',

        -- Comercial transitorio
        'venta_transito',
        'factura_interna_detalle',
        'factura_interna',

        -- Compras
        'compra_legal_detalle',
        'compra_legal_pedido',
        'compra_legal',

        -- Pedido proveedor
        'pedido_proveedor_detalle',
        'pedido_proveedor',

        -- Intención de compra
        'intencion_compra_detalle',
        'intencion_compra',

        -- Catálogo legacy
        'producto_v2'
    ];
    existentes text[] := ARRAY[]::text[];
    t text;
BEGIN
    FOREACH t IN ARRAY candidatas LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            existentes := array_append(existentes, format('public.%I', t));
            RAISE NOTICE '· truncando %', t;
        ELSE
            RAISE NOTICE '· se omite % (no existe)', t;
        END IF;
    END LOOP;

    IF cardinality(existentes) > 0 THEN
        -- CASCADE solo arrastra tablas que REFERENCIAN a las nombradas (hijos
        -- operativos como compra_legal_detalle); nunca cascadea hacia maestras.
        EXECUTE 'TRUNCATE TABLE ' || array_to_string(existentes, ', ') || ' RESTART IDENTITY CASCADE';
        RAISE NOTICE '== Reset operativo OK: % tablas truncadas con IDs a 1 ==',
            cardinality(existentes);
    END IF;
END $$;

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN — todo lo operativo debe quedar en 0.
-- Los pilares deben seguir intactos (linea: 1451, referencia: 1251, etc.).
-- ═══════════════════════════════════════════════════════════════════════════
SELECT 'pedido_proveedor'              AS tabla, COUNT(*) FROM public.pedido_proveedor UNION ALL
SELECT 'pedido_proveedor_detalle',                COUNT(*) FROM public.pedido_proveedor_detalle UNION ALL
SELECT 'intencion_compra',                        COUNT(*) FROM public.intencion_compra UNION ALL
SELECT 'compra_legal',                            COUNT(*) FROM public.compra_legal UNION ALL
SELECT 'compra_legal_pedido',                     COUNT(*) FROM public.compra_legal_pedido UNION ALL
SELECT 'traspaso',                                COUNT(*) FROM public.traspaso UNION ALL
SELECT 'traspaso_detalle',                        COUNT(*) FROM public.traspaso_detalle UNION ALL
SELECT 'movimiento',                              COUNT(*) FROM public.movimiento UNION ALL
SELECT 'movimiento_detalle',                      COUNT(*) FROM public.movimiento_detalle UNION ALL
SELECT 'combinacion',                             COUNT(*) FROM public.combinacion UNION ALL
SELECT 'precio_lista',                            COUNT(*) FROM public.precio_lista UNION ALL
SELECT 'pedido_web',                              COUNT(*) FROM public.pedido_web UNION ALL
SELECT 'pedido_web_detalle',                      COUNT(*) FROM public.pedido_web_detalle UNION ALL
-- Pilares (deben tener filas):
SELECT '— pilares —',                              NULL UNION ALL
SELECT 'linea (pilar)',                           COUNT(*) FROM public.linea UNION ALL
SELECT 'referencia (pilar)',                      COUNT(*) FROM public.referencia UNION ALL
SELECT 'linea_referencia (pilar)',                COUNT(*) FROM public.linea_referencia UNION ALL
SELECT 'marca_v2 (pilar)',                        COUNT(*) FROM public.marca_v2 UNION ALL
SELECT 'genero (pilar)',                          COUNT(*) FROM public.genero UNION ALL
SELECT 'grupo_estilo_v2 (pilar)',                 COUNT(*) FROM public.grupo_estilo_v2 UNION ALL
SELECT 'material (pilar)',                        COUNT(*) FROM public.material UNION ALL
SELECT 'color (pilar)',                           COUNT(*) FROM public.color UNION ALL
SELECT 'talla (pilar)',                           COUNT(*) FROM public.talla UNION ALL
SELECT 'caso_precio_biblioteca (pilar)',          COUNT(*) FROM public.caso_precio_biblioteca UNION ALL
SELECT 'precio_evento (pilar)',                   COUNT(*) FROM public.precio_evento UNION ALL
SELECT 'precio_evento_caso (pilar)',              COUNT(*) FROM public.precio_evento_caso;
