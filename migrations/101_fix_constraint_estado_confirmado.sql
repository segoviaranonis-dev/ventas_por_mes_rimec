-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 101: FIX - Agregar CONFIRMADO al constraint de estados
-- FECHA: 2026-05-28
-- URGENCIA: CRÍTICA
--
-- PROBLEMA: El CHECK CONSTRAINT de pedido_venta_rimec.estado NO permite 'CONFIRMADO'
--           Esto hace que los pedidos queden atascados en PENDIENTE incluso cuando
--           todas sus FIs están CONFIRMADAS.
--
-- FLUJO CORRECTO:
--   PENDIENTE   → Pedido creado desde rimec-web, esperando confirmación de FIs
--   CONFIRMADO  → Todas las FIs fueron confirmadas, esperando autorización final
--   AUTORIZADO  → Pedido autorizado para procesamiento
--   RECHAZADO   → Pedido rechazado
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. Eliminar constraint antigua ────────────────────────────────────────
ALTER TABLE public.pedido_venta_rimec
DROP CONSTRAINT IF EXISTS pedido_venta_rimec_estado_check;

-- ── 2. Crear constraint actualizado ────────────────────────────────────────
ALTER TABLE public.pedido_venta_rimec
ADD CONSTRAINT pedido_venta_rimec_estado_check
CHECK (estado IN ('PENDIENTE', 'CONFIRMADO', 'AUTORIZADO', 'RECHAZADO'));

COMMENT ON CONSTRAINT pedido_venta_rimec_estado_check ON public.pedido_venta_rimec IS
'Estados válidos: PENDIENTE (inicial) → CONFIRMADO (FIs aprobadas) → AUTORIZADO (procesable) | RECHAZADO';

-- ── 3. Actualizar pedidos que deberían estar en CONFIRMADO ─────────────────
-- Cambiar a CONFIRMADO todos los pedidos PENDIENTES donde TODAS las FIs están CONFIRMADAS
UPDATE public.pedido_venta_rimec pvr
SET estado = 'CONFIRMADO'
WHERE pvr.estado = 'PENDIENTE'
  AND EXISTS (
      SELECT 1
      FROM public.factura_interna fi
      WHERE fi.pedido_id = pvr.id
      GROUP BY fi.pedido_id
      HAVING COUNT(*) > 0
         AND COUNT(*) FILTER (WHERE fi.estado = 'CONFIRMADA') = COUNT(*)
  );

COMMIT;

SELECT 'MIG-101 OK: Constraint actualizado y pedidos corregidos' AS estado;
