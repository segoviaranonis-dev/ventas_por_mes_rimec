-- 093: Vista SQL optimizada para módulo de aprobaciones
-- Elimina el waterfall de consultas: trae pedidos + clientes + vendedores en una sola query

CREATE OR REPLACE VIEW v_aprobaciones_detalladas AS
SELECT
    p.id,
    p.nro_pedido,
    p.created_at AS fecha_creacion,
    p.vendedor_id,
    p.cliente_id,
    p.total_monto,
    p.total_pares,
    p.estado,
    p.plazo_id,
    p.lista_precio_id,
    p.descuento_1,
    p.descuento_2,
    p.descuento_3,
    p.descuento_4,
    p.fecha_aprobacion,
    p.fecha_rechazo,
    p.aprobado_por_id,
    p.rechazado_por_id,
    p.motivo_rechazo,

    -- Datos del cliente
    c.descp_cliente AS cliente_nombre,

    -- Datos del vendedor
    v.descp_usuario AS vendedor_nombre

FROM pedido_venta_rimec p
LEFT JOIN cliente_v2 c ON p.cliente_id = c.id_cliente
LEFT JOIN usuario_v2 v ON p.vendedor_id = v.id_usuario

ORDER BY p.id DESC;

-- Grant de permisos para Supabase anon
GRANT SELECT ON v_aprobaciones_detalladas TO anon;
GRANT SELECT ON v_aprobaciones_detalladas TO authenticated;
