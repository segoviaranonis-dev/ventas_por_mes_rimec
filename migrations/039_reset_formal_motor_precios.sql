-- ═══════════════════════════════════════════════════════════════════════════
-- 039 — Arranque formal Motor de Precios (post 037/038)
--
-- Elimina eventos de prueba (ej. CP-0421-PP-4333x) y reinicia contadores a 1.
-- NO toca: linea, listado_precio (LPN/LPC03/LPC04). Vacía caso_precio_biblioteca (ver 040).
-- Desvincula IC/ICP antes de TRUNCATE por FK a precio_evento.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

UPDATE public.intencion_compra
SET precio_evento_id = NULL
WHERE precio_evento_id IS NOT NULL;

UPDATE public.intencion_compra_pedido
SET precio_evento_id = NULL
WHERE precio_evento_id IS NOT NULL;

TRUNCATE TABLE
    public.precio_auditoria,
    public.precio_evento_linea_excepcion,
    public.precio_lista,
    public.precio_evento_caso,
    public.precio_evento
RESTART IDENTITY CASCADE;

-- NO incluir caso_precio_biblioteca en TRUNCATE CASCADE: borra linea por FK caso_id.
DELETE FROM public.caso_precio_biblioteca;
SELECT setval(
    pg_get_serial_sequence('public.caso_precio_biblioteca', 'id'),
    1,
    false
);

COMMIT;

-- Verificación (todo en 0; próximo evento = id 1)
SELECT 'precio_evento' AS tabla, COUNT(*) AS n FROM public.precio_evento
UNION ALL SELECT 'precio_evento_caso', COUNT(*) FROM public.precio_evento_caso
UNION ALL SELECT 'precio_evento_linea_excepcion', COUNT(*) FROM public.precio_evento_linea_excepcion
UNION ALL SELECT 'precio_lista', COUNT(*) FROM public.precio_lista
UNION ALL SELECT 'caso_precio_biblioteca (debe 0)', COUNT(*) FROM public.caso_precio_biblioteca
UNION ALL SELECT 'linea con caso_id', COUNT(*) FROM public.linea WHERE caso_id IS NOT NULL;
