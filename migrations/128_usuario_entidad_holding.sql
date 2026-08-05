-- DEPRECATED: usar migración 129 (ente_id → entes). Este archivo queda solo como historial local.
--
-- Separa explícitamente usuarios RIMEC y BAZZAR (empresa holding).
-- Complementa rol_id + categoria — ver MATRIZ_ROLES_ACCESOS_HOLDING.md
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE public.usuario_v2
  ADD COLUMN IF NOT EXISTS entidad_holding text;

UPDATE public.usuario_v2
SET entidad_holding = CASE
  WHEN rol_id = 2 THEN 'BAZZAR'
  ELSE 'RIMEC'
END
WHERE entidad_holding IS NULL OR btrim(entidad_holding) = '';

ALTER TABLE public.usuario_v2
  ALTER COLUMN entidad_holding SET DEFAULT 'RIMEC';

ALTER TABLE public.usuario_v2
  ALTER COLUMN entidad_holding SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_usuario_v2_entidad_holding'
  ) THEN
    ALTER TABLE public.usuario_v2
      ADD CONSTRAINT chk_usuario_v2_entidad_holding
      CHECK (entidad_holding IN ('RIMEC', 'BAZZAR'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_usuario_v2_entidad_holding
  ON public.usuario_v2 (entidad_holding);

COMMENT ON COLUMN public.usuario_v2.entidad_holding IS
  'Empresa holding del usuario: RIMEC (importadora) | BAZZAR (retail). Distinto de entes/tiendas.';

COMMIT;
