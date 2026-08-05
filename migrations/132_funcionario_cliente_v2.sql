-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 132: funcionarios.id_cliente → cliente_v2 (origen canónico 2100…)
--
-- Regla Director:
--   Punto operativo / codigo cliente = FK cliente_v2.id_cliente (descp_cliente)
--   NO punto_ente_id ni entes hoja para RRHH
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE public.funcionarios
  ADD COLUMN IF NOT EXISTS id_cliente BIGINT REFERENCES public.cliente_v2(id_cliente) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_funcionarios_id_cliente
  ON public.funcionarios (id_cliente)
  WHERE id_cliente IS NOT NULL;

COMMENT ON COLUMN public.funcionarios.id_cliente IS
  'Punto operativo Bazzar — FK cliente_v2.id_cliente (2100, 2400…). Descripcion en descp_cliente.';

-- Backfill desde punto_ente_id → entes.cliente_id → cliente_v2
UPDATE public.funcionarios f
SET id_cliente = e.cliente_id
FROM public.entes e
WHERE f.punto_ente_id = e.id_ente
  AND e.cliente_id IS NOT NULL
  AND f.id_cliente IS NULL
  AND EXISTS (SELECT 1 FROM public.cliente_v2 c WHERE c.id_cliente = e.cliente_id);

ALTER TABLE public.funcionarios DROP COLUMN IF EXISTS punto_ente_id;

COMMIT;
