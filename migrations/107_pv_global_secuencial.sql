-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 107: Número PV Global Secuencial (Robusto)
--
-- CONTEXTO:
--   El número de factura actual (1-PV014, 8-PV015) es por PP, no global.
--   MAMACHA necesita numeración GLOBAL secuencial (PV000001 → PV000071)
--   para todas las FIs que "realmente existieron" (CONFIRMADA o ANULADA).
--
-- OBJETIVOS:
--   1. Agregar columna `pv_global` (INTEGER UNIQUE NOT NULL)
--   2. Backfill con ROW_NUMBER() por created_at
--   3. Solo numerar: CONFIRMADA + ANULADA (excluir RESERVADA)
--   4. Auto-incrementar en nuevas inserciones
--
-- RESULTADO:
--   - PV000001: Primera FI creada (CONFIRMADA o ANULADA)
--   - PV000071: Última FI creada (actual)
--   - nro_factura: Legacy (1-PV014, mantener intacto)
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── 1. Agregar columna pv_global ──────────────────────────────────────────
ALTER TABLE public.factura_interna
  ADD COLUMN IF NOT EXISTS pv_global INTEGER;

-- ── 2. Guardar definición del constraint chk_vendedor_rol ────────────────
DO $$
DECLARE
  v_constraint_def TEXT;
BEGIN
  SELECT pg_get_constraintdef(oid)
  INTO v_constraint_def
  FROM pg_constraint
  WHERE conname = 'chk_vendedor_rol'
    AND conrelid = 'public.factura_interna'::regclass
  LIMIT 1;

  -- Guardar para referencia (en caso de que falle)
  RAISE NOTICE 'Constraint original: %', v_constraint_def;
END$$;

-- ── 3. Eliminar temporalmente el constraint ───────────────────────────────
ALTER TABLE public.factura_interna DROP CONSTRAINT IF EXISTS chk_vendedor_rol;

-- ── 4. Backfill: Asignar números secuenciales a FIs existentes ───────────
WITH fis_numeradas AS (
  SELECT
    id,
    ROW_NUMBER() OVER (ORDER BY created_at ASC) AS seq
  FROM public.factura_interna
  WHERE estado IN ('CONFIRMADA', 'ANULADA')
)
UPDATE public.factura_interna fi
SET pv_global = fn.seq
FROM fis_numeradas fn
WHERE fi.id = fn.id;

-- ── 5. Recrear el constraint ───────────────────────────────────────────────
ALTER TABLE public.factura_interna
  ADD CONSTRAINT chk_vendedor_rol
  CHECK (
    (vendedor_id IS NULL) OR
    fn_es_usuario_vendedor_o_admin(vendedor_id)
  ) NOT VALID;  -- NOT VALID = no valida filas existentes, solo nuevas inserciones

-- ── 6. Aplicar NOT NULL + UNIQUE después del backfill ─────────────────────
-- (Solo a registros CONFIRMADA/ANULADA, RESERVADA puede quedar NULL)
DO $$
BEGIN
  -- Validar que no hay NULLs en CONFIRMADA/ANULADA
  IF EXISTS (
    SELECT 1 FROM public.factura_interna
    WHERE estado IN ('CONFIRMADA', 'ANULADA')
      AND pv_global IS NULL
  ) THEN
    RAISE EXCEPTION 'Error: Hay FIs CONFIRMADA/ANULADA sin pv_global';
  END IF;

  -- Crear constraint UNIQUE solo si no existe
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema = 'public'
      AND table_name = 'factura_interna'
      AND constraint_name = 'factura_interna_pv_global_key'
  ) THEN
    -- UNIQUE solo en filas con pv_global no-NULL
    CREATE UNIQUE INDEX factura_interna_pv_global_key
      ON public.factura_interna (pv_global)
      WHERE pv_global IS NOT NULL;
    RAISE NOTICE 'Constraint UNIQUE en pv_global creado';
  ELSE
    RAISE NOTICE 'Constraint pv_global ya existía';
  END IF;
END$$;

-- ── 7. Función: Asignar pv_global automáticamente al confirmar/anular ─────
CREATE OR REPLACE FUNCTION public.asignar_pv_global()
RETURNS TRIGGER AS $$
BEGIN
  -- Solo asignar si estado cambia a CONFIRMADA o ANULADA y aún no tiene pv_global
  IF NEW.estado IN ('CONFIRMADA', 'ANULADA') AND NEW.pv_global IS NULL THEN
    SELECT COALESCE(MAX(pv_global), 0) + 1
    INTO NEW.pv_global
    FROM public.factura_interna
    WHERE pv_global IS NOT NULL;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ── 8. Trigger: Ejecutar antes de INSERT o UPDATE ─────────────────────────
DROP TRIGGER IF EXISTS trigger_asignar_pv_global ON public.factura_interna;
CREATE TRIGGER trigger_asignar_pv_global
  BEFORE INSERT OR UPDATE ON public.factura_interna
  FOR EACH ROW
  EXECUTE FUNCTION public.asignar_pv_global();

COMMIT;

-- ═══════════════════════════════════════════════════════════════════════════
-- VERIFICACIÓN:
-- ═══════════════════════════════════════════════════════════════════════════
-- SELECT estado, COUNT(*) as total, MIN(pv_global) as min_pv, MAX(pv_global) as max_pv
-- FROM public.factura_interna
-- GROUP BY estado
-- ORDER BY estado;
--
-- SELECT pv_global, nro_factura, estado, created_at
-- FROM public.factura_interna
-- WHERE pv_global IS NOT NULL
-- ORDER BY pv_global DESC
-- LIMIT 10;
-- ═══════════════════════════════════════════════════════════════════════════
