-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 131: Ente principal en usuario · punto cliente en RRHH
--
-- Regla Director:
--   usuario_v2.ente_id  → solo ente principal (sin cliente_id: cod 1–5)
--   funcionarios.punto_ente_id → FK hoja entes (2100, 2400…) — RRHH
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE public.funcionarios
  ADD COLUMN IF NOT EXISTS punto_ente_id INTEGER REFERENCES public.entes(id_ente) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_funcionarios_punto_ente
  ON public.funcionarios (punto_ente_id)
  WHERE punto_ente_id IS NOT NULL;

COMMENT ON COLUMN public.funcionarios.ente_id IS
  'Ente principal holding (RIMEC, Fernando, San Martín…) — sin codigo cliente tablet.';

COMMENT ON COLUMN public.funcionarios.punto_ente_id IS
  'Punto operativo / cliente tablet (2100 Adultos, 2900 Niños…) — FK entes hoja con cliente_id.';

-- Si funcionario estaba en hoja, mover a punto_ente_id y subir ente al padre
UPDATE public.funcionarios f
SET
  punto_ente_id = e.id_ente,
  ente_id = COALESCE(e.parent_id_ente, f.ente_id)
FROM public.entes e
WHERE f.ente_id = e.id_ente
  AND e.cliente_id IS NOT NULL
  AND f.punto_ente_id IS NULL;

-- Usuarios en hoja → ente principal padre
UPDATE public.usuario_v2 u
SET ente_id = e.parent_id_ente
FROM public.entes e
WHERE u.ente_id = e.id_ente
  AND e.cliente_id IS NOT NULL
  AND e.parent_id_ente IS NOT NULL;

UPDATE public.usuario_v2 u
SET ente_id = (SELECT id_ente FROM public.entes WHERE codigo = 1 LIMIT 1)
FROM public.entes e
WHERE u.ente_id = e.id_ente
  AND e.cliente_id IS NOT NULL
  AND e.parent_id_ente IS NULL
  AND e.codigo = 12;

-- Reforzar ley triada: ente usuario = principal
CREATE OR REPLACE FUNCTION public.fn_validar_usuario_triada()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_cat_nivel int2;
  v_rol_nivel int2;
  v_ente_codigo int;
  v_ente_cliente int;
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

  SELECT e.codigo, e.cliente_id INTO v_ente_codigo, v_ente_cliente
  FROM public.entes e
  WHERE e.id_ente = NEW.ente_id;

  IF v_cat_nivel IS NULL OR v_rol_nivel IS NULL THEN
    RAISE EXCEPTION 'LEY TRIADA: categoria_id y rol_id válidos requeridos';
  END IF;

  IF v_ente_codigo IS NULL THEN
    RAISE EXCEPTION 'ente_id requerido — tabla entes principal (sin cliente_id)';
  END IF;

  IF v_ente_cliente IS NOT NULL THEN
    RAISE EXCEPTION 'usuario_v2.ente_id debe ser ente principal (RIMEC/tienda). Codigo cliente va en funcionarios.punto_ente_id (RRHH)';
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

COMMIT;
