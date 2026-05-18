-- ═══════════════════════════════════════════════════════════════════════════
-- 024 — Reset eventos de precio (limpieza de "vestigios" del historial)
--
-- Borra los eventos de precio puntuales (carga del 23-abr, 04-may, etc.) y los
-- listados asociados, dejando solo los CASOS genéricos (la "biblioteca").
--
-- Tras esta migración:
--   · caso_precio_biblioteca       → CONSERVADO (4 filas: "LPN normal", etc.)
--   · caso_precio_biblioteca_linea → CONSERVADO (vacío o no, no se toca)
--   · precio_evento                → TRUNCATE (los 8 vestigios desaparecen)
--   · precio_evento_caso           → TRUNCATE
--   · precio_evento_linea_excepcion → TRUNCATE
--   · listado_precio               → ⚠ NO TOCAR (catálogo canónico, ver 027)
--   · lista_precio                 → TRUNCATE
--   · listado_de_precio_v2         → TRUNCATE (si existe)
--
-- Reinicia los IDs a 1 para que el próximo evento sea ID = 1.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

DO $$
DECLARE
    candidatas text[] := ARRAY[
        'precio_evento_linea_excepcion',
        'precio_evento_caso',
        'precio_evento',
        -- 'listado_precio' es CATÁLOGO (LPN/LPC02/LPC03/LPC04). Repoblar con 027.
        'lista_precio',
        'listado_de_precio_v2'
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
        EXECUTE 'TRUNCATE TABLE ' || array_to_string(existentes, ', ') || ' RESTART IDENTITY CASCADE';
        RAISE NOTICE '== Eventos de precio reseteados: % tablas truncadas con IDs a 1 ==',
            cardinality(existentes);
    END IF;
END $$;

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN
-- Eventos/listados → 0. Casos (biblioteca) → conservados.
-- ═══════════════════════════════════════════════════════════════════════════
SELECT 'precio_evento'                  AS tabla, COUNT(*) FROM public.precio_evento UNION ALL
SELECT 'precio_evento_caso',                       COUNT(*) FROM public.precio_evento_caso UNION ALL
SELECT 'precio_evento_linea_excepcion',            COUNT(*) FROM public.precio_evento_linea_excepcion UNION ALL
SELECT 'listado_precio',                           COUNT(*) FROM public.listado_precio UNION ALL
SELECT 'lista_precio',                             COUNT(*) FROM public.lista_precio UNION ALL
SELECT 'listado_de_precio_v2',                     COUNT(*) FROM public.listado_de_precio_v2 UNION ALL
SELECT 'precio_lista (renglones, debe seguir 0)',  COUNT(*) FROM public.precio_lista UNION ALL
-- Pilares de precio que deben seguir intactos:
SELECT '— casos biblioteca (pilar) —',             NULL UNION ALL
SELECT 'caso_precio_biblioteca',                   COUNT(*) FROM public.caso_precio_biblioteca UNION ALL
SELECT 'caso_precio_biblioteca_linea',             COUNT(*) FROM public.caso_precio_biblioteca_linea;
