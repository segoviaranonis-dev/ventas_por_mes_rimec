-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 095: Formalización de Estados de Pedido Venta RIMEC
--
-- CONTEXTO:
--   El flujo de confirmación de Facturas Internas requiere un estado intermedio
--   entre PENDIENTE y AUTORIZADO. Este estado se llama CONFIRMADO.
--
-- FLUJO DE ESTADOS:
--   PENDIENTE   → El pedido fue creado desde RIMEC WEB, esperando aprobación
--   CONFIRMADO  → Todas las Facturas Internas fueron confirmadas, listo para autorización final
--   AUTORIZADO  → El pedido fue autorizado y está listo para procesamiento
--   RECHAZADO   → El pedido fue rechazado
--
-- FLUJO PARALELO DE FACTURAS INTERNAS:
--   RESERVADA   → La FI fue creada y reservó stock (soft-lock)
--   CONFIRMADA  → La FI fue aprobada por el director/supervisor
--   ANULADA     → La FI fue rechazada y se revirtió el stock
--
-- INTEGRACIÓN CON EMAIL + PDF:
--   Cuando TODAS las FIs de un pedido están en CONFIRMADA:
--     1. El PVR cambia de PENDIENTE → CONFIRMADO
--     2. Se genera un PDF multi-factura con todas las FIs
--     3. Se envía email automático al vendedor y supervisor con el PDF adjunto
--
-- AUTOR: Héctor & Claude AI
-- FECHA: 2026-05-26
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. Agregar comentario a columna estado ─────────────────────────────────
COMMENT ON COLUMN public.pedido_venta_rimec.estado IS
'Estados válidos: PENDIENTE (inicial), CONFIRMADO (todas FIs aprobadas), AUTORIZADO (procesable), RECHAZADO';

COMMENT ON COLUMN public.factura_interna.estado IS
'Estados válidos: RESERVADA (stock reservado), CONFIRMADA (aprobada), ANULADA (rechazada con reversión de stock)';

-- ── 2. Índice para búsqueda por estado (optimización) ──────────────────────
CREATE INDEX IF NOT EXISTS idx_pedido_venta_rimec_estado
ON public.pedido_venta_rimec (estado);

CREATE INDEX IF NOT EXISTS idx_factura_interna_estado
ON public.factura_interna (estado);

-- ── 3. Vista helper: Resumen de estado de pedidos ──────────────────────────
CREATE OR REPLACE VIEW public.v_pedido_estado_resumen AS
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
LEFT JOIN public.factura_interna fi ON fi.id_pedido_venta_rimec = pvr.id
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
'Vista helper para dashboard de aprobaciones. Muestra estado de PVR y contadores de FIs.';

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN:
-- ═══════════════════════════════════════════════════════════════════════════
-- -- Ver distribución de estados
-- SELECT estado, COUNT(*)
-- FROM public.pedido_venta_rimec
-- GROUP BY estado;
--
-- SELECT estado, COUNT(*)
-- FROM public.factura_interna
-- GROUP BY estado;
--
-- -- Ver pedidos con todas las FIs confirmadas
-- SELECT * FROM public.v_pedido_estado_resumen
-- WHERE todas_fis_confirmadas = TRUE;
-- ═══════════════════════════════════════════════════════════════════════════
