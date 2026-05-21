-- 062 — RESET FOCAL: IC + Pedido Proveedor + Digitación + Listados de precios
-- OT: OT-RESET-FOCAL-IC-PP-LISTADOS-001
-- Director: Héctor Segovia · Fecha: 2026-05-20
--
-- Alcance ACOTADO (no es OT-511):
--   Borra: intencion_compra(+pedido), pedido_proveedor(+detalle, snapshot),
--          precio_evento(+caso, lista, excepcion, auditoria)
--   Conserva: pilares, biblioteca, diccionario web, Sales Report, Retail,
--             factura_interna, compra_legal, traspaso, movimiento, pedido_web
--
-- IMPORTANTE: si hay filas en factura_interna / compra_legal / traspaso /
-- movimiento / pedido_web, este reset NO debe ejecutarse (usar OT-511 completa).
-- El script Python valida ese pre-requisito; este SQL es para SQL Editor manual.

BEGIN;

-- ── FASE 1: Desvincular FKs precio_evento ─────────────────────────────────────

UPDATE intencion_compra SET precio_evento_id = NULL
WHERE precio_evento_id IS NOT NULL;

UPDATE intencion_compra_pedido SET precio_evento_id = NULL
WHERE precio_evento_id IS NOT NULL;

-- Si existe la columna (depende de migración rama biblioteca):
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='precio_evento'
      AND column_name='biblioteca_precio_id'
  ) THEN
    UPDATE precio_evento SET biblioteca_precio_id = NULL
    WHERE biblioteca_precio_id IS NOT NULL;
  END IF;
END $$;

-- ── FASE 2: TRUNCATE Intención + Pedido Proveedor + Digitación ────────────────
-- intencion_compra_pedido = tabla puente de Digitación

TRUNCATE TABLE
  intencion_compra_pedido,
  intencion_compra,
  snapshot_costos,
  pedido_proveedor_detalle,
  pedido_proveedor
RESTART IDENTITY CASCADE;

-- ── FASE 3: TRUNCATE Listados de precios (sin biblioteca) ─────────────────────

TRUNCATE TABLE
  precio_auditoria,
  precio_evento_linea_excepcion,
  precio_lista,
  precio_evento_caso,
  precio_evento
RESTART IDENTITY CASCADE;

-- NO TOCAR:
--   linea, referencia, linea_referencia, material, color, talla       (pilares)
--   caso_precio_biblioteca, biblioteca_precio, biblioteca_caso_linea  (biblioteca)
--   caso_precio_web_regla                                             (diccionario web)
--   registro_ventas_general_v2                                        (Sales Report)
--   registro_st_vt_rc_reposicion                                      (Retail)
--   factura_interna*, compra_legal*, traspaso*, movimiento*, pedido_web*

COMMIT;

-- ── POST-VERIFICACIÓN MANUAL ──────────────────────────────────────────────────
-- SELECT 'intencion_compra' AS tabla, COUNT(*) FROM intencion_compra
-- UNION ALL SELECT 'intencion_compra_pedido', COUNT(*) FROM intencion_compra_pedido
-- UNION ALL SELECT 'pedido_proveedor', COUNT(*) FROM pedido_proveedor
-- UNION ALL SELECT 'pedido_proveedor_detalle', COUNT(*) FROM pedido_proveedor_detalle
-- UNION ALL SELECT 'snapshot_costos', COUNT(*) FROM snapshot_costos
-- UNION ALL SELECT 'precio_evento', COUNT(*) FROM precio_evento
-- UNION ALL SELECT 'precio_lista', COUNT(*) FROM precio_lista
-- UNION ALL SELECT 'caso_precio_biblioteca', COUNT(*) FROM caso_precio_biblioteca   -- > 0 (conservado)
-- UNION ALL SELECT 'biblioteca_caso_linea', COUNT(*) FROM biblioteca_caso_linea     -- > 0 (conservado)
-- UNION ALL SELECT 'linea', COUNT(*) FROM linea                                     -- > 0 (pilar)
-- UNION ALL SELECT 'registro_ventas_general_v2', COUNT(*) FROM registro_ventas_general_v2  -- intacto
-- UNION ALL SELECT 'registro_st_vt_rc_reposicion', COUNT(*) FROM registro_st_vt_rc_reposicion;
