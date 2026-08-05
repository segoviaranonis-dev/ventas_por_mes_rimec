-- MIG-123 · Web origen clients_bazaar → tienda_cliente_id 5000
UPDATE public.clients_bazaar
SET
  registro_tienda_cliente_id = COALESCE(registro_tienda_cliente_id, 5000),
  ultimo_tienda_cliente_id = COALESCE(ultimo_tienda_cliente_id, 5000)
WHERE registro_ente_codigo = 5 OR canal_registro = 'WEB';

COMMENT ON COLUMN public.clients_bazaar.registro_tienda_cliente_id IS
  'Tablet: 2100|2900|2400|2700|3100|3200. Web Bazzar: 5000 (cliente_v2 canal e-commerce).';
