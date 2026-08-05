-- 116 · Proveedor importación Kyly (confecciones 638)
-- Prerequisito import tipo_v2_id=2 con pilares FK

INSERT INTO public.proveedor_importacion (id, codigo, nombre, pais, moneda_default, activo)
OVERRIDING SYSTEM VALUE
VALUES (638, '638', 'KYLY CONFECCIONES', 'Brasil', 'USD', true)
ON CONFLICT (id) DO UPDATE SET
  codigo = EXCLUDED.codigo,
  nombre = EXCLUDED.nombre,
  pais = EXCLUDED.pais,
  moneda_default = EXCLUDED.moneda_default,
  activo = EXCLUDED.activo;

COMMENT ON TABLE public.proveedor_importacion IS
  'Importadores de pilares: 654 calzado Beira Rio · 638 confecciones Kyly';
