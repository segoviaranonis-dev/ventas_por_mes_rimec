-- 118 — Permitir el mismo nombre_caso en bibliotecas distintas (clon bib→bib).
-- Antes: UNIQUE (proveedor_id, nombre_caso) → copiar = mover.
-- Después: UNIQUE (biblioteca_id, nombre_caso) → copiar = clonar.

BEGIN;

DO $$
DECLARE
  cname text;
BEGIN
  FOR cname IN
    SELECT con.conname
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    WHERE nsp.nspname = 'public'
      AND rel.relname = 'caso_precio_biblioteca'
      AND con.contype = 'u'
      AND pg_get_constraintdef(con.oid) ~ 'proveedor_id'
      AND pg_get_constraintdef(con.oid) ~ 'nombre_caso'
  LOOP
    EXECUTE format('ALTER TABLE public.caso_precio_biblioteca DROP CONSTRAINT %I', cname);
  END LOOP;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'caso_precio_biblioteca_biblioteca_nombre_uq'
  ) THEN
    ALTER TABLE public.caso_precio_biblioteca
      ADD CONSTRAINT caso_precio_biblioteca_biblioteca_nombre_uq
      UNIQUE (biblioteca_id, nombre_caso);
  END IF;
END $$;

COMMENT ON CONSTRAINT caso_precio_biblioteca_biblioteca_nombre_uq ON public.caso_precio_biblioteca IS
  'MIG-118: nombre_caso único por biblioteca; clon entre bibliotecas del mismo proveedor.';

COMMIT;

SELECT '118 aplicada: unique caso por biblioteca_id + nombre_caso' AS estado;
