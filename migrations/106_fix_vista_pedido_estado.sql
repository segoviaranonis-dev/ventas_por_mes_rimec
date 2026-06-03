-- =============================================================================
-- MIGRACION 106: Fix vista v_pedido_estado_resumen (bug migración 095)
--
-- PROBLEMA:
--   Migración 095 creó vista con JOIN incorrecto:
--     LEFT JOIN public.factura_interna fi ON fi.id_pedido_venta_rimec = pvr.id
--   Pero la columna real es: fi.pedido_id (no id_pedido_venta_rimec)
--
-- SINTOMA:
--   - FIs confirmadas SÍ tienen pedido_id correcto
--   - Pero NO aparecen en pantalla "Aprobaciones"
--   - Vista cuenta 0 facturas para cada pedido
--
-- SOLUCION:
--   Recrear vista con JOIN correcto: fi.pedido_id = pvr.id
--
-- AUTOR: YAMBAI (investigación pedido PV000007)
-- FECHA: 2026-06-03
-- =============================================================================

BEGIN;

-- Eliminar vista rota
DROP VIEW IF EXISTS public.v_pedido_estado_resumen CASCADE;

-- Recrear vista con JOIN CORRECTO
CREATE VIEW public.v_pedido_estado_resumen AS
SELECT
    pvr.id,
    pvr.nro_pedido,
    pvr.estado as pedido_estado,
    pvr.cliente_id,
    c.descp_cliente as cliente_nombre,
    pvr.vendedor_id,
    v.descp_usuario as vendedor_nombre,
    pvr.total_pares,
    pvr.total_monto,
    pvr.created_at,
    -- Estadísticas de Facturas Internas
    COUNT(fi.id) as total_facturas,
    COUNT(fi.id) FILTER (WHERE fi.estado = 'RESERVADA') as fis_reservadas,
    COUNT(fi.id) FILTER (WHERE fi.estado = 'CONFIRMADA') as fis_confirmadas,
    COUNT(fi.id) FILTER (WHERE fi.estado = 'ANULADA') as fis_anuladas,
    -- Indicador: ¿Todas confirmadas?
    CASE
        WHEN COUNT(fi.id) > 0
             AND COUNT(fi.id) FILTER (WHERE fi.estado = 'CONFIRMADA') = COUNT(fi.id)
        THEN TRUE
        ELSE FALSE
    END as todas_fis_confirmadas
FROM public.pedido_venta_rimec pvr
LEFT JOIN public.cliente_v2 c ON c.id_cliente = pvr.cliente_id
LEFT JOIN public.usuario_v2 v ON v.id_usuario = pvr.vendedor_id
-- FIX: Usar fi.pedido_id (columna real) en lugar de fi.id_pedido_venta_rimec (no existe)
LEFT JOIN public.factura_interna fi ON fi.pedido_id = pvr.id
WHERE pvr.estado IN ('PENDIENTE', 'CONFIRMADO', 'AUTORIZADO')
GROUP BY
    pvr.id,
    pvr.nro_pedido,
    pvr.estado,
    pvr.cliente_id,
    c.descp_cliente,
    pvr.vendedor_id,
    v.descp_usuario,
    pvr.total_pares,
    pvr.total_monto,
    pvr.created_at
ORDER BY pvr.created_at DESC;

COMMENT ON VIEW public.v_pedido_estado_resumen IS
'Vista helper para dashboard de aprobaciones. Muestra estado de PVR y contadores de FIs. [FIX MIG-106: JOIN correcto con fi.pedido_id]';

COMMIT;

-- =============================================================================
-- VERIFICACION:
-- =============================================================================
-- -- Ver pedidos con facturas (debería mostrar > 0 ahora)
-- SELECT
--     nro_pedido,
--     pedido_estado,
--     total_facturas,
--     fis_confirmadas,
--     fis_reservadas
-- FROM public.v_pedido_estado_resumen
-- WHERE total_facturas > 0
-- ORDER BY created_at DESC
-- LIMIT 10;
--
-- -- Verificar caso PV000007
-- SELECT
--     pvr.nro_pedido,
--     COUNT(fi.id) as facturas_asociadas,
--     STRING_AGG(fi.nro_factura, ', ') as numeros_fi
-- FROM public.pedido_venta_rimec pvr
-- LEFT JOIN public.factura_interna fi ON fi.pedido_id = pvr.id
-- WHERE fi.nro_factura LIKE '%00007%'
-- GROUP BY pvr.id, pvr.nro_pedido;
-- =============================================================================
