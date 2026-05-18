-- ═══════════════════════════════════════════════════════════════════════════
-- 027 — Repoblar catálogo canónico de listado_precio
--
-- Contexto:
--   La migración 024 truncó listado_precio asumiendo que era transaccional.
--   En realidad es CATÁLOGO (4 listados canónicos referenciados por FK desde
--   intencion_compra, precio_lista, etc.). Sin esos 4 IDs, todo INSERT que
--   referencie listado_precio_id = 1..4 falla con FK violation.
--
-- IDs canónicos del sistema (NO tocar):
--   1 → LPN    (precio neto / referencia base)
--   2 → LPC02  (corte interno · excluido del selector de PROGRAMADO)
--   3 → LPC03  (LPN + 12 %)
--   4 → LPC04  (LPN + 20 %)
--
-- Idempotente: si la fila ya existe, actualiza nombre/descripcion/activo.
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- La columna id está definida como GENERATED ALWAYS AS IDENTITY, por eso
-- usamos OVERRIDING SYSTEM VALUE para forzar los IDs canónicos del sistema.
INSERT INTO public.listado_precio (id, nombre, descripcion, activo)
OVERRIDING SYSTEM VALUE
VALUES
    (1, 'LPN',   'Precio neto · referencia base',            TRUE),
    (2, 'LPC02', 'Listado interno · no se ofrece en PROGRAMADO', TRUE),
    (3, 'LPC03', 'LPN + 12%',                                 TRUE),
    (4, 'LPC04', 'LPN + 20%',                                 TRUE)
ON CONFLICT (id) DO UPDATE
SET nombre      = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    activo      = EXCLUDED.activo;

-- Realineamos la sequence de identidad para que el próximo INSERT "natural"
-- (sin OVERRIDING) arranque después del último canónico.
SELECT setval(
    pg_get_serial_sequence('public.listado_precio', 'id'),
    GREATEST(4, (SELECT COALESCE(MAX(id), 0) FROM public.listado_precio))
);

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN
-- ═══════════════════════════════════════════════════════════════════════════
SELECT id, nombre, descripcion, activo
FROM public.listado_precio
ORDER BY id;
