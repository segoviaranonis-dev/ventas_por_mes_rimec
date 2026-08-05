-- =============================================================================
-- MIGRACIÓN 119: Bloqueo de usuarios + governance holding
-- Protocolo: PROTOCOLO_BITACORA_USUARIOS_Y_REVERSIONES.md
-- =============================================================================

BEGIN;

ALTER TABLE public.usuario_v2
  ADD COLUMN IF NOT EXISTS bloqueado boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS bloqueado_motivo text,
  ADD COLUMN IF NOT EXISTS bloqueado_at timestamptz,
  ADD COLUMN IF NOT EXISTS bloqueado_por bigint REFERENCES public.usuario_v2(id_usuario);

CREATE INDEX IF NOT EXISTS idx_usuario_v2_bloqueado
  ON public.usuario_v2 (bloqueado)
  WHERE bloqueado = true;

COMMENT ON COLUMN public.usuario_v2.bloqueado IS
  'true = login denegado en Nexus/Report. Solo holding desbloquea vía OT.';
COMMENT ON COLUMN public.usuario_v2.bloqueado_motivo IS
  'Motivo forense del bloqueo (comportamiento inapropiado, fraude, etc.)';

COMMIT;
