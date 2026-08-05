-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 129: usuario_v2 → entes (canónico RRHH / holding)
--
-- Revierte entidad_holding (128) si existió — absurdo paralelo.
-- Enlaza usuarios a public.entes (RIMEC, tiendas, puntos Bazzar + codigo cliente).
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. Ampliar catálogo entes (mismo que RRHH + codigo cliente tablet) ──
ALTER TABLE public.entes
  ADD COLUMN IF NOT EXISTS cliente_id INTEGER;

CREATE UNIQUE INDEX IF NOT EXISTS idx_entes_cliente_id
  ON public.entes (cliente_id)
  WHERE cliente_id IS NOT NULL;

COMMENT ON COLUMN public.entes.cliente_id IS
  'Codigo cliente tablet / deposito (2100 Fernando Adultos, 2900 Niños, …). NULL = empresa o tienda agregada.';

-- Puntos Bazzar con codigo cliente (paridad depositos-config / tablet)
INSERT INTO public.entes (codigo, nombre, tipo, cliente_id) VALUES
  (6,  'Fernando · Adultos',    'tienda', 2100),
  (7,  'Fernando · Niños',      'tienda', 2900),
  (8,  'San Martín · Adultos',  'tienda', 2400),
  (9,  'San Martín · Niños',    'tienda', 2700),
  (10, 'Palma · Adultos',       'tienda', 3100),
  (11, 'Palma · Niños',         'tienda', 3200)
ON CONFLICT (codigo) DO UPDATE SET
  nombre = EXCLUDED.nombre,
  tipo = EXCLUDED.tipo,
  cliente_id = EXCLUDED.cliente_id,
  activo = true;

-- Web Bazzar e-commerce
INSERT INTO public.entes (codigo, nombre, tipo, cliente_id) VALUES
  (12, 'Bazzar Web · E-commerce', 'empresa', 5000)
ON CONFLICT (codigo) DO UPDATE SET
  nombre = EXCLUDED.nombre,
  cliente_id = EXCLUDED.cliente_id,
  activo = true;

-- ── 2. Quitar columna absurda 128 si llegó a aplicarse ──
ALTER TABLE public.usuario_v2 DROP CONSTRAINT IF EXISTS chk_usuario_v2_entidad_holding;
DROP INDEX IF EXISTS idx_usuario_v2_entidad_holding;
ALTER TABLE public.usuario_v2 DROP COLUMN IF EXISTS entidad_holding;

-- ── 3. FK usuario → ente (misma tabla que funcionarios.ente_id) ──
ALTER TABLE public.usuario_v2
  ADD COLUMN IF NOT EXISTS ente_id INTEGER REFERENCES public.entes(id_ente) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_usuario_v2_ente_id ON public.usuario_v2 (ente_id);

COMMENT ON COLUMN public.usuario_v2.ente_id IS
  'Ente holding del usuario — FK entes.id_ente (RIMEC cod.1, tiendas Bazzar + cliente_id tablet).';

-- Backfill: rol Bazzar → Fernando Adultos; resto → RIMEC
UPDATE public.usuario_v2 u
SET ente_id = e.id_ente
FROM public.entes e
WHERE u.ente_id IS NULL
  AND (
    (u.rol_id = 2 AND e.codigo = 6)
    OR (u.rol_id <> 2 AND e.codigo = 1)
  );

COMMIT;
