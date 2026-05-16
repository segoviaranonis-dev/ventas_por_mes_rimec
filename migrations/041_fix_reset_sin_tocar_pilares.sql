-- ═══════════════════════════════════════════════════════════════════════════
-- 041 — CORRECCIÓN: vaciar biblioteca SIN CASCADE
--
-- ERROR en 039/040/--reset anterior: TRUNCATE caso_precio_biblioteca CASCADE
-- eliminó public.linea (FK linea.caso_id → caso_precio_biblioteca) y en cadena
-- referencia / linea_referencia.
--
-- Esta migración solo vacía biblioteca y eventos de precio. NO usa CASCADE
-- sobre tablas referenciadas por linea.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

UPDATE public.intencion_compra SET precio_evento_id = NULL WHERE precio_evento_id IS NOT NULL;
UPDATE public.intencion_compra_pedido SET precio_evento_id = NULL WHERE precio_evento_id IS NOT NULL;

TRUNCATE TABLE
    public.precio_auditoria,
    public.precio_evento_linea_excepcion,
    public.precio_lista,
    public.precio_evento_caso,
    public.precio_evento
RESTART IDENTITY CASCADE;

DELETE FROM public.caso_precio_biblioteca;
SELECT setval(
    pg_get_serial_sequence('public.caso_precio_biblioteca', 'id'),
    1,
    false
);

COMMIT;

SELECT 'linea' AS tabla, COUNT(*)::bigint AS n FROM public.linea
UNION ALL SELECT 'linea_referencia', COUNT(*) FROM public.linea_referencia
UNION ALL SELECT 'referencia', COUNT(*) FROM public.referencia
UNION ALL SELECT 'caso_precio_biblioteca', COUNT(*) FROM public.caso_precio_biblioteca
UNION ALL SELECT 'precio_evento', COUNT(*) FROM public.precio_evento;
