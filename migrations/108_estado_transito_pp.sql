-- Migración 108: Agregar estado_transito a pedido_proveedor
-- Fecha: 2026-06-03
-- Autor: Héctor + Claude
-- Objetivo: Controlar disponibilidad en rimec-web según estado real del PP

-- 1. Agregar columna estado_transito
ALTER TABLE public.pedido_proveedor
ADD COLUMN IF NOT EXISTS estado_transito VARCHAR(50) DEFAULT 'EN_TRANSITO';

-- 2. Comentario explicativo
COMMENT ON COLUMN public.pedido_proveedor.estado_transito IS
'Estado del PP en el flujo de tránsito. Valores:
- PROFORMA: Creado, no enviado a proveedor
- EN_TRANSITO: Enviado desde Brasil, vendible en rimec-web (Pre-Venta)
- ARRIBADO: Llegó a Paraguay, esperando descarga
- EN_DEPOSITO: En depósito físico, NO vendible en rimec-web (Stock)
- AGOTADO: Todo distribuido/vendido';

-- 3. Actualizar PPs existentes: todos EN_TRANSITO por defecto
-- (Los que estén en depósito se marcarán cuando finalicen compra)
UPDATE public.pedido_proveedor
SET estado_transito = 'EN_TRANSITO'
WHERE estado_transito IS NULL;

-- 4. Crear índice para performance en rimec-web
CREATE INDEX IF NOT EXISTS idx_pp_estado_transito
ON public.pedido_proveedor(estado_transito)
WHERE estado_transito = 'EN_TRANSITO';

-- 5. Verificación
DO $$
DECLARE
    total_pp INTEGER;
    en_transito INTEGER;
    en_deposito INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_pp FROM public.pedido_proveedor;
    SELECT COUNT(*) INTO en_transito FROM public.pedido_proveedor WHERE estado_transito = 'EN_TRANSITO';
    SELECT COUNT(*) INTO en_deposito FROM public.pedido_proveedor WHERE estado_transito = 'EN_DEPOSITO';

    RAISE NOTICE '✓ Migración 108 completada';
    RAISE NOTICE '  Total PPs: %', total_pp;
    RAISE NOTICE '  EN_TRANSITO: %', en_transito;
    RAISE NOTICE '  EN_DEPOSITO: %', en_deposito;
END $$;