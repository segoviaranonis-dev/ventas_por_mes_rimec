-- 117 · Multi-proveedor: quitar UNIQUE legacy solo codigo_proveedor (colisiona 654 vs 638)
-- Ley triplete: UNIQUE (proveedor_id, codigo_proveedor) ya existe desde migración 004.

ALTER TABLE public.color DROP CONSTRAINT IF EXISTS color_codigo_key;
ALTER TABLE public.material DROP CONSTRAINT IF EXISTS material_codigo_key;

COMMENT ON TABLE public.color IS
  'Pilar color — UNIQUE (proveedor_id, codigo_proveedor); sin UNIQUE global legacy';
