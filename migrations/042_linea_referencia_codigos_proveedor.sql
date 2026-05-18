-- 042 — linea_referencia: códigos de negocio además de FK (proveedor, línea, referencia)

ALTER TABLE public.linea_referencia
    ADD COLUMN IF NOT EXISTS codigo_proveedor TEXT,
    ADD COLUMN IF NOT EXISTS linea_codigo_proveedor BIGINT,
    ADD COLUMN IF NOT EXISTS referencia_codigo_proveedor BIGINT;

COMMENT ON COLUMN public.linea_referencia.codigo_proveedor IS
    'Código de negocio del importador (proveedor_importacion.codigo), además de proveedor_id.';

COMMENT ON COLUMN public.linea_referencia.linea_codigo_proveedor IS
    'Código numérico de línea (linea.codigo_proveedor), denormalizado para consulta.';

COMMENT ON COLUMN public.linea_referencia.referencia_codigo_proveedor IS
    'Código numérico de referencia (referencia.codigo_proveedor), denormalizado.';

UPDATE public.linea_referencia lr
SET codigo_proveedor = pi.codigo::text,
    linea_codigo_proveedor = l.codigo_proveedor,
    referencia_codigo_proveedor = r.codigo_proveedor
FROM public.linea l,
     public.referencia r,
     public.proveedor_importacion pi
WHERE lr.linea_id = l.id
  AND lr.referencia_id = r.id
  AND lr.proveedor_id = pi.id;
