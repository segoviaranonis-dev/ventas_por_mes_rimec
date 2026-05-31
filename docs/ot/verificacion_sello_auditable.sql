-- =============================================================================
-- QUERIES DE VERIFICACIÓN — OT-NEXUS-PP-SELLO-AUDITABLE-003
-- Uso: Ejecutar DESPUÉS de presionar "Pasar a Compra" en un PP
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Verificar que PP fue sellado correctamente
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    id,
    numero_registro,
    estado,
    -- Auditoría temporal
    enviado_at,
    enviado_por,
    cerrado_at,
    cerrado_por,
    -- Datos operativos
    categoria_id,
    pares_comprometidos,
    created_at
FROM pedido_proveedor
WHERE id = :id_pp;

-- Esperado:
--   - estado = 'ENVIADO'
--   - enviado_at IS NOT NULL (timestamp del sellado)
--   - enviado_por IS NOT NULL (usuario que selló)
--   - cerrado_at IS NOT NULL (mismo que enviado_at)
--   - cerrado_por IS NOT NULL (mismo usuario)

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Verificar vínculo con Compra Legal y snapshot
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    clp.id,
    clp.compra_legal_id,
    clp.pedido_proveedor_id,
    -- Snapshot auditable
    clp.categoria_id,
    clp.precio_evento_id,
    clp.pares_snapshot,
    clp.snapshot_at
FROM compra_legal_pedido clp
WHERE clp.pedido_proveedor_id = :id_pp;

-- Esperado:
--   - categoria_id coincide con PP.categoria_id
--   - precio_evento_id viene de intencion_compra_pedido
--   - pares_snapshot coincide con PP.pares_comprometidos
--   - snapshot_at es timestamp del sellado

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Verificar que Compra Legal recibió snapshot
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    cl.id,
    cl.numero_registro,
    cl.estado,
    -- Snapshot de categoría/tipo/precio
    cl.categoria_id,
    cl.tipo_v2_id,
    cl.precio_evento_id,
    -- Operativo
    cl.numero_factura_proveedor,
    cl.created_at
FROM compra_legal cl
JOIN compra_legal_pedido clp ON clp.compra_legal_id = cl.id
WHERE clp.pedido_proveedor_id = :id_pp;

-- Esperado:
--   - categoria_id, tipo_v2_id, precio_evento_id coinciden con el PP
--   - Si hay múltiples PPs, refleja categoría predominante

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Verificar log de auditoría de cambio de estado
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    id,
    pp_id,
    estado_anterior,
    estado_nuevo,
    timestamp,
    usuario_id,
    compra_legal_id,
    observaciones
FROM pedido_proveedor_log
WHERE pp_id = :id_pp
ORDER BY timestamp DESC;

-- Esperado:
--   - Al menos 1 registro con estado_nuevo = 'ENVIADO'
--   - usuario_id coincide con enviado_por
--   - compra_legal_id coincide con la CL creada
--   - observaciones describe el sellado

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Query de verificación completa (JOIN de todas las tablas)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    -- PP
    pp.id AS pp_id,
    pp.numero_registro AS pp_numero,
    pp.estado,
    pp.enviado_at,
    pp.enviado_por,
    pp.categoria_id AS pp_categoria,
    pp.pares_comprometidos,
    -- Snapshot en CLP
    clp.categoria_id AS clp_categoria_snapshot,
    clp.precio_evento_id AS clp_precio_evento_snapshot,
    clp.pares_snapshot AS clp_pares_snapshot,
    clp.snapshot_at,
    -- Compra Legal
    cl.id AS cl_id,
    cl.numero_registro AS cl_numero,
    cl.categoria_id AS cl_categoria_snapshot,
    cl.tipo_v2_id AS cl_tipo_snapshot,
    cl.precio_evento_id AS cl_precio_evento_snapshot,
    -- Log
    log.timestamp AS log_timestamp,
    log.estado_nuevo AS log_estado,
    log.observaciones AS log_obs
FROM pedido_proveedor pp
LEFT JOIN compra_legal_pedido clp ON clp.pedido_proveedor_id = pp.id
LEFT JOIN compra_legal cl ON cl.id = clp.compra_legal_id
LEFT JOIN pedido_proveedor_log log ON log.pp_id = pp.id AND log.estado_nuevo = 'ENVIADO'
WHERE pp.id = :id_pp;

-- Esperado (todos NOT NULL si sellado fue exitoso):
--   - pp.enviado_at, enviado_por
--   - clp.categoria_id, precio_evento_id, pares_snapshot, snapshot_at
--   - cl.categoria_id, tipo_v2_id, precio_evento_id
--   - log.timestamp, log_estado, log_obs

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Prueba de idempotencia (detectar duplicados)
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    compra_legal_id,
    pedido_proveedor_id,
    COUNT(*) AS duplicados
FROM compra_legal_pedido
GROUP BY compra_legal_id, pedido_proveedor_id
HAVING COUNT(*) > 1;

-- Esperado: 0 filas (UNIQUE constraint debe prevenir duplicados)

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Verificar que precio_evento_id se recuperó correctamente
-- ─────────────────────────────────────────────────────────────────────────────
SELECT
    pp.id AS pp_id,
    pp.numero_registro,
    icp.precio_evento_id AS precio_evento_original,
    clp.precio_evento_id AS precio_evento_snapshot,
    CASE
        WHEN icp.precio_evento_id = clp.precio_evento_id THEN 'MATCH'
        WHEN icp.precio_evento_id IS NULL THEN 'SIN_PRECIO_EVENTO'
        ELSE 'MISMATCH'
    END AS validacion
FROM pedido_proveedor pp
LEFT JOIN intencion_compra_pedido icp ON icp.pedido_proveedor_id = pp.id
LEFT JOIN compra_legal_pedido clp ON clp.pedido_proveedor_id = pp.id
WHERE pp.id = :id_pp;

-- Esperado: validacion = 'MATCH'

-- =============================================================================
-- FIN QUERIES DE VERIFICACIÓN
-- =============================================================================
