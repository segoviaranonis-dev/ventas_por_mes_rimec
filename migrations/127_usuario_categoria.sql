-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 127: Catálogo normalizado de categorías de usuario (holding)
--
-- Contexto:
--   usuario_v2.rol_id  → FK public.maestro_rol_acceso(id)
--   usuario_v2.categoria → texto libre hoy (DIOS, ADMIN, VENDEDOR, …)
--
-- Esta tabla normaliza categorías por rol (empresa holding) para el módulo
-- LOCAL de administración visual de usuarios en Report (/pilares/usuarios).
-- NO altera usuario_v2 en esta migración (fase 2: categoria_id).
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS public.usuario_categoria (
  id_categoria   SERIAL PRIMARY KEY,
  rol_id         int2 NOT NULL REFERENCES public.maestro_rol_acceso(id) ON DELETE RESTRICT,
  codigo         text NOT NULL,
  descripcion    text,
  activo         boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_usuario_categoria_rol_codigo UNIQUE (rol_id, codigo),
  CONSTRAINT chk_usuario_categoria_codigo_no_vacio CHECK (btrim(codigo) <> '')
);

CREATE INDEX IF NOT EXISTS idx_usuario_categoria_rol_id
  ON public.usuario_categoria (rol_id);

CREATE INDEX IF NOT EXISTS idx_usuario_categoria_activo
  ON public.usuario_categoria (activo)
  WHERE activo = true;

COMMENT ON TABLE public.usuario_categoria IS
  'Catálogo holding de categorías por rol (empresa). Matiza permisos dentro de usuario_v2.rol_id.';

COMMENT ON COLUMN public.usuario_categoria.rol_id IS
  'FK → maestro_rol_acceso.id · mismo campo que usuario_v2.rol_id (holding: 1=RIMEC, 2=BAZZAR).';

COMMENT ON COLUMN public.usuario_categoria.codigo IS
  'Código canónico UPPER (DIOS, ADMIN, VENDEDOR, …). Par único con rol_id.';

-- Semilla canónica — matriz holding (MATRIZ_ROLES_ACCESOS_HOLDING.md)
INSERT INTO public.usuario_categoria (rol_id, codigo, descripcion) VALUES
  (1, 'DIOS',     'Nivel Dios · acceso total holding (rol_id=1)'),
  (1, 'ADMIN',    'Administrador RIMEC · todo Report salvo Aprobaciones si no es DIOS'),
  (1, 'VENDEDOR', 'Vendedor RIMEC · Report solo ventas-fotos'),
  (2, 'ADMIN',    'Administrador Bazzar · Report solo módulos Bazzar'),
  (2, 'VENDEDOR', 'Vendedor Bazzar · tablet POS · sin Report web')
ON CONFLICT (rol_id, codigo) DO UPDATE SET
  descripcion = EXCLUDED.descripcion,
  activo = true,
  updated_at = now();

COMMIT;
