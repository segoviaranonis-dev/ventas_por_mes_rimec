-- ═══════════════════════════════════════════════════════════════════════════
-- 040 — Vaciar biblioteca SIN tocar pilares
-- NO usar TRUNCATE ... CASCADE (destruye linea). Solo DELETE.
-- Preferir: migrations/041_fix_reset_sin_tocar_pilares.sql
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

DELETE FROM public.caso_precio_biblioteca;
SELECT setval(
    pg_get_serial_sequence('public.caso_precio_biblioteca', 'id'),
    1,
    false
);

COMMIT;

SELECT COUNT(*) AS filas_biblioteca FROM public.caso_precio_biblioteca;
SELECT COUNT(*) AS lineas_pilar FROM public.linea;
