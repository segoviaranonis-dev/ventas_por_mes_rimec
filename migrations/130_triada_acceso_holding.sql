-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 130: Triada acceso holding — Ente × Rol orgánico × Categoría
--
-- Ley Director:
--   · Menor número = más poder (nivel 1 > nivel 2 > nivel 3 …)
--   · categoria.nivel >= rol.nivel (categoría no puede ser superior al rol)
--   · DIOS: ente RIMEC (cod 1) + rol GERENTE (nivel 1) + categoria DIOS (nivel 1)
--   · Ente = scope sesión (árbol holding + cliente_id en hojas)
--   · rol_id → maestro_rol_acceso = rol ORGÁNICO (ya no “empresa”)
--   · funcionario_id opcional en ejecutores / externos (rotativa tienda)
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. Árbol entes ───────────────────────────────────────────────────────
ALTER TABLE public.entes
  ADD COLUMN IF NOT EXISTS parent_id_ente INTEGER REFERENCES public.entes(id_ente) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_entes_parent_id ON public.entes (parent_id_ente);

COMMENT ON COLUMN public.entes.parent_id_ente IS
  'Padre en árbol holding: RIMEC(1) → tiendas → puntos cliente (2100, 2900…).';

UPDATE public.entes c
SET parent_id_ente = p.id_ente
FROM public.entes p
WHERE c.parent_id_ente IS NULL
  AND p.codigo = 1
  AND c.codigo IN (2, 3, 4, 5, 12);

UPDATE public.entes c
SET parent_id_ente = p.id_ente
FROM public.entes p
WHERE c.parent_id_ente IS NULL AND p.codigo = 2 AND c.codigo IN (6, 7);

UPDATE public.entes c
SET parent_id_ente = p.id_ente
FROM public.entes p
WHERE c.parent_id_ente IS NULL AND p.codigo = 3 AND c.codigo IN (8, 9);

UPDATE public.entes c
SET parent_id_ente = p.id_ente
FROM public.entes p
WHERE c.parent_id_ente IS NULL AND p.codigo = 4 AND c.codigo IN (10, 11);

-- ── 2. Rol orgánico (repurpose maestro_rol_acceso) ─────────────────────────
ALTER TABLE public.maestro_rol_acceso
  ADD COLUMN IF NOT EXISTS nivel int2;

UPDATE public.maestro_rol_acceso SET
  nivel = id,
  nombre_rol = CASE id
    WHEN 1 THEN 'GERENTE'
    WHEN 2 THEN 'ADMINISTRADOR'
    WHEN 3 THEN 'EJECUTOR'
    WHEN 4 THEN 'EXTERNO'
    ELSE nombre_rol
  END,
  descripcion = CASE id
    WHEN 1 THEN 'Gerentes · nivel 1 · máximo rol orgánico'
    WHEN 2 THEN 'Administradores · nivel 2'
    WHEN 3 THEN 'Ejecutores / vendedores tienda · nivel 3 · RRHH opcional'
    WHEN 4 THEN 'Externo / rotativa · nivel 4 · sin RRHH obligatorio'
    ELSE descripcion
  END
WHERE nivel IS NULL OR id <= 4;

ALTER TABLE public.maestro_rol_acceso
  ALTER COLUMN nivel SET NOT NULL;

COMMENT ON TABLE public.maestro_rol_acceso IS
  'Rol orgánico holding (usuario_v2.rol_id). Nivel 1=Gerente … 4=Externo. NO es empresa.';

COMMENT ON COLUMN public.maestro_rol_acceso.nivel IS
  'Jerarquía orgánica: menor = más autoridad. Matiza con usuario_categoria.nivel.';

-- ── 3. Categorías globales (sin rol_id por empresa) ────────────────────────
ALTER TABLE public.usuario_categoria
  ADD COLUMN IF NOT EXISTS nivel int2;

UPDATE public.usuario_categoria SET nivel = CASE UPPER(TRIM(codigo))
  WHEN 'DIOS' THEN 1
  WHEN 'ADMIN' THEN 2
  WHEN 'VENDEDOR' THEN 3
  WHEN 'VENDEDORES' THEN 3
  WHEN 'OPERARIO' THEN 4
  ELSE COALESCE(nivel, 4)
END
WHERE nivel IS NULL;

ALTER TABLE public.usuario_categoria DROP CONSTRAINT IF EXISTS usuario_categoria_rol_id_fkey;
ALTER TABLE public.usuario_categoria DROP CONSTRAINT IF EXISTS uq_usuario_categoria_rol_codigo;
ALTER TABLE public.usuario_categoria DROP COLUMN IF EXISTS rol_id;

DELETE FROM public.usuario_categoria a
USING public.usuario_categoria b
WHERE a.id_categoria > b.id_categoria
  AND UPPER(a.codigo) = UPPER(b.codigo);

ALTER TABLE public.usuario_categoria
  ALTER COLUMN nivel SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_usuario_categoria_codigo'
  ) THEN
    ALTER TABLE public.usuario_categoria
      ADD CONSTRAINT uq_usuario_categoria_codigo UNIQUE (codigo);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_usuario_categoria_nivel'
  ) THEN
    ALTER TABLE public.usuario_categoria
      ADD CONSTRAINT uq_usuario_categoria_nivel UNIQUE (nivel);
  END IF;
END $$;

INSERT INTO public.usuario_categoria (nivel, codigo, descripcion) VALUES
  (1, 'DIOS',     'Nivel Dios · acceso total · solo RIMEC + rol GERENTE'),
  (2, 'ADMIN',    'Administrador · acceso amplio según módulo'),
  (3, 'VENDEDOR', 'Operativo · tablet venta / ventas-fotos según ente'),
  (4, 'OPERARIO', 'Operario depósito / logística · acceso acotado')
ON CONFLICT (codigo) DO UPDATE SET
  nivel = EXCLUDED.nivel,
  descripcion = EXCLUDED.descripcion,
  activo = true,
  updated_at = now();

COMMENT ON TABLE public.usuario_categoria IS
  'Poder de acceso apps. nivel 1=DIOS … 4=OPERARIO. Ley: categoria.nivel >= rol.nivel del usuario.';

COMMENT ON COLUMN public.usuario_categoria.nivel IS
  'Menor = más poder. Usuario solo puede tener categoria.nivel >= maestro_rol_acceso.nivel.';

-- ── 4. usuario_v2 — FK categoría + RRHH ────────────────────────────────────
ALTER TABLE public.usuario_v2
  ADD COLUMN IF NOT EXISTS categoria_id INTEGER REFERENCES public.usuario_categoria(id_categoria) ON DELETE RESTRICT;

ALTER TABLE public.usuario_v2
  ADD COLUMN IF NOT EXISTS funcionario_id INTEGER REFERENCES public.funcionarios(id_funcionario) ON DELETE SET NULL;

ALTER TABLE public.usuario_v2
  ADD COLUMN IF NOT EXISTS es_externo BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_usuario_v2_categoria_id ON public.usuario_v2 (categoria_id);
CREATE INDEX IF NOT EXISTS idx_usuario_v2_funcionario_id ON public.usuario_v2 (funcionario_id);

COMMENT ON COLUMN public.usuario_v2.rol_id IS
  'FK maestro_rol_acceso — rol ORGÁNICO (1 Gerente, 2 Admin, 3 Ejecutor, 4 Externo). Scope empresa = ente_id.';

COMMENT ON COLUMN public.usuario_v2.categoria_id IS
  'FK usuario_categoria — poder en apps. Debe cumplir categoria.nivel >= rol.nivel.';

COMMENT ON COLUMN public.usuario_v2.funcionario_id IS
  'FK funcionarios — obligatorio gerentes/admins; opcional ejecutores; exento si es_externo.';

COMMENT ON COLUMN public.usuario_v2.es_externo IS
  'Usuario externo / rotativa — exento de vínculo RRHH obligatorio.';

UPDATE public.usuario_v2 u
SET categoria_id = c.id_categoria
FROM public.usuario_categoria c
WHERE u.categoria_id IS NULL
  AND UPPER(TRIM(u.categoria)) = UPPER(TRIM(c.codigo));

UPDATE public.usuario_v2 u
SET categoria_id = c.id_categoria
FROM public.usuario_categoria c
WHERE u.categoria_id IS NULL
  AND UPPER(TRIM(u.categoria)) = 'SU'
  AND c.codigo = 'ADMIN';

-- Heurística rol orgánico desde categoría legacy (revisar en admin visual)
UPDATE public.usuario_v2 u
SET rol_id = CASE
  WHEN UPPER(TRIM(u.categoria)) = 'DIOS' THEN 1
  WHEN UPPER(TRIM(u.categoria)) IN ('ADMIN', 'SU', 'DIRECTOR', 'ROOT') THEN 2
  ELSE 3
END
WHERE u.rol_id IS NULL OR u.rol_id IN (1, 2, 3);

-- ── 5. Ley triada (trigger) ────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.fn_validar_usuario_triada()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_cat_nivel int2;
  v_rol_nivel int2;
  v_ente_codigo int;
  v_cat_codigo text;
BEGIN
  IF NEW.categoria_id IS NULL THEN
    SELECT id_categoria INTO NEW.categoria_id
    FROM public.usuario_categoria
    WHERE UPPER(TRIM(codigo)) = UPPER(TRIM(COALESCE(NEW.categoria, '')))
    LIMIT 1;
  END IF;

  SELECT c.nivel, c.codigo INTO v_cat_nivel, v_cat_codigo
  FROM public.usuario_categoria c
  WHERE c.id_categoria = NEW.categoria_id;

  SELECT r.nivel INTO v_rol_nivel
  FROM public.maestro_rol_acceso r
  WHERE r.id = NEW.rol_id;

  SELECT e.codigo INTO v_ente_codigo
  FROM public.entes e
  WHERE e.id_ente = NEW.ente_id;

  IF v_cat_nivel IS NULL OR v_rol_nivel IS NULL THEN
    RAISE EXCEPTION 'LEY TRIADA: categoria_id y rol_id válidos requeridos';
  END IF;

  IF v_cat_nivel < v_rol_nivel THEN
    RAISE EXCEPTION 'LEY TRIADA: categoría (nivel %) no puede ser superior al rol (nivel %)',
      v_cat_nivel, v_rol_nivel;
  END IF;

  IF v_cat_nivel = 1 THEN
    IF v_rol_nivel <> 1 OR COALESCE(v_ente_codigo, 999) <> 1 THEN
      RAISE EXCEPTION 'DIOS requiere ente RIMEC (cod 1), rol GERENTE (nivel 1) y categoría DIOS (nivel 1)';
    END IF;
  END IF;

  IF NEW.categoria IS NULL OR btrim(NEW.categoria) = '' THEN
    NEW.categoria := v_cat_codigo;
  END IF;

  IF NOT COALESCE(NEW.es_externo, false)
     AND NEW.funcionario_id IS NULL
     AND v_rol_nivel <= 2 THEN
    RAISE EXCEPTION 'Gerentes y administradores requieren funcionario_id (RRHH) salvo es_externo';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_usuario_v2_triada ON public.usuario_v2;
CREATE TRIGGER trg_usuario_v2_triada
  BEFORE INSERT OR UPDATE OF rol_id, categoria_id, categoria, ente_id, funcionario_id, es_externo
  ON public.usuario_v2
  FOR EACH ROW
  EXECUTE FUNCTION public.fn_validar_usuario_triada();

-- ── 6. Catálogo módulos tablet (semilla) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS public.modulo_acceso_requisito (
  id_requisito     SERIAL PRIMARY KEY,
  producto         text NOT NULL,
  codigo_modulo    text NOT NULL,
  nombre_modulo    text NOT NULL,
  ente_codigo_min  int2,
  ente_codigo_max  int2,
  rol_nivel_max    int2 NOT NULL DEFAULT 3,
  categoria_nivel_max int2 NOT NULL DEFAULT 3,
  activo           boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_modulo_acceso_producto_codigo UNIQUE (producto, codigo_modulo)
);

COMMENT ON TABLE public.modulo_acceso_requisito IS
  'Requisitos por módulo. Acceso si user.ente/rol/categoria cumplen max (menor número = más poder).';

INSERT INTO public.modulo_acceso_requisito
  (producto, codigo_modulo, nombre_modulo, ente_codigo_min, ente_codigo_max, rol_nivel_max, categoria_nivel_max)
VALUES
  ('TABLET_BAZZAR', 'ALL',           'Tablet completa',     1, 99, 1, 2),
  ('TABLET_BAZZAR', 'DEPOSITO',      'Depósito tablet',     2, 99, 2, 2),
  ('TABLET_BAZZAR', 'VENTA',         'Venta POS',           2, 99, 3, 3),
  ('TABLET_BAZZAR', 'ESTADISTICAS',  'Estadísticas del día', 2, 99, 2, 2),
  ('REPORT',        'APROBACIONES',  'Aprobaciones',        1, 1,  1, 1),
  ('REPORT',        'VENTAS_FOTOS',  'Ventas + fotos',      1, 1,  3, 3)
ON CONFLICT (producto, codigo_modulo) DO UPDATE SET
  nombre_modulo = EXCLUDED.nombre_modulo,
  ente_codigo_min = EXCLUDED.ente_codigo_min,
  ente_codigo_max = EXCLUDED.ente_codigo_max,
  rol_nivel_max = EXCLUDED.rol_nivel_max,
  categoria_nivel_max = EXCLUDED.categoria_nivel_max,
  activo = true;

COMMIT;
