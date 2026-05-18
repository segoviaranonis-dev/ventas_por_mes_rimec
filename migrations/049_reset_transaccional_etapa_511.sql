-- 049 — OT-RESET-TRANSACCIONAL-511-001: Reset operativa mayo 2026
-- Conserva pilares + biblioteca + diccionario Web
-- Anti-patrón: NO usar TRUNCATE CASCADE en caso_precio_biblioteca (039/041)

-- IMPORTANTE: Ejecutar primero el script Python para pre/post validation
-- Esta migración es opcional — reproducible si se necesita aplicar en Supabase SQL Editor

BEGIN;

-- ── FASE 1: Desvincular FKs precio_evento_id ──────────────────────────────

UPDATE intencion_compra SET precio_evento_id = NULL
WHERE precio_evento_id IS NOT NULL;

UPDATE intencion_compra_pedido SET precio_evento_id = NULL
WHERE precio_evento_id IS NOT NULL;

-- Si columna existe:
UPDATE precio_evento SET biblioteca_precio_id = NULL
WHERE biblioteca_precio_id IS NOT NULL;

-- ── FASE 2: TRUNCATE tablas operativas ────────────────────────────────────

TRUNCATE TABLE
  intencion_compra_pedido,
  intencion_compra,
  snapshot_costos,
  pedido_proveedor_detalle,
  pedido_proveedor,
  factura_interna_detalle,
  factura_interna,
  compra_legal_detalle,
  compra_legal_pedido,
  compra_legal,
  traspaso_detalle,
  traspaso,
  movimiento_detalle,
  movimiento,
  combinacion,
  pedido_web_detalle,
  pedido_web,
  pedido_venta_rimec,
  cliente_web,
  venta_transito,
  flujo_auditoria,
  retail_multitienda_staging
RESTART IDENTITY CASCADE;

-- ── FASE 3: TRUNCATE eventos precio (sin biblioteca) ──────────────────────

TRUNCATE TABLE
  precio_auditoria,
  precio_evento_linea_excepcion,
  precio_lista,
  precio_evento_caso,
  precio_evento
RESTART IDENTITY CASCADE;

-- NO truncar: caso_precio_biblioteca, biblioteca_precio, biblioteca_caso_linea
-- NO truncar: linea, referencia, material, color, talla
-- NO truncar: caso_precio_web_regla (OT-509)
-- NO truncar: registro_ventas_general_v2 (blindado)

COMMIT;

-- ── POST-VERIFICACIÓN MANUAL ───────────────────────────────────────────────

-- Verificar pilares intactos:
-- SELECT COUNT(*) FROM linea;           -- esperado: 1452
-- SELECT COUNT(*) FROM referencia;      -- esperado: 10679
-- SELECT COUNT(*) FROM material;        -- esperado: 29239

-- Verificar biblioteca intacta:
-- SELECT COUNT(*) FROM caso_precio_biblioteca;  -- esperado: 5
-- SELECT COUNT(*) FROM biblioteca_caso_linea;   -- esperado: 5807

-- Verificar diccionario Web:
-- SELECT COUNT(*) FROM caso_precio_web_regla;   -- esperado: 6

-- Verificar operativa vaciada:
-- SELECT COUNT(*) FROM pedido_proveedor;        -- esperado: 0
-- SELECT COUNT(*) FROM precio_evento;           -- esperado: 0
-- SELECT COUNT(*) FROM movimiento_detalle;      -- esperado: 0

-- Sales Report blindado:
-- SELECT COUNT(*) FROM registro_ventas_general_v2;  -- esperado: 107570
