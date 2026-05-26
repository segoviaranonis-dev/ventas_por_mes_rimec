-- ============================================================================
-- MIGRACIÓN 097: Agregar FK quincena_arribo_id (SIN ROMPER campos antiguos)
-- AUTOR: Héctor & Claude AI
-- FECHA: 2026-05-26
-- ESTRATEGIA: Dual-field - Mantener campos viejos, agregar nuevos en paralelo
-- ============================================================================

-- 1. INTENCIÓN DE COMPRA
-- Mantiene: fecha de registro (lo que tenga)
-- Agrega: quincena_arribo_id (FK nullable)
ALTER TABLE public.intencion_compra
ADD COLUMN IF NOT EXISTS quincena_arribo_id INTEGER REFERENCES public.quincena_arribo(id);

COMMENT ON COLUMN public.intencion_compra.quincena_arribo_id IS
'FK a quincena_arribo (1-24). Campo NUEVO - convive con fecha antigua hasta migración completa';

-- 2. PEDIDO PROVEEDOR
-- Mantiene: fecha_arribo_estimada, descripcion_arribo, fecha_arribo, fecha_arribo_real
-- Agrega: quincena_arribo_id (FK nullable)
ALTER TABLE public.pedido_proveedor
ADD COLUMN IF NOT EXISTS quincena_arribo_id INTEGER REFERENCES public.quincena_arribo(id);

COMMENT ON COLUMN public.pedido_proveedor.quincena_arribo_id IS
'FK a quincena_arribo (1-24). FUENTE DE VERDAD final. Campo NUEVO - convive con fecha_arribo_estimada';

-- 3. FACTURA INTERNA
-- Mantiene: lo que tenga de fechas
-- Agrega: quincena_arribo_id (FK nullable) - dato de cabecera para reportes
ALTER TABLE public.factura_interna
ADD COLUMN IF NOT EXISTS quincena_arribo_id INTEGER REFERENCES public.quincena_arribo(id);

COMMENT ON COLUMN public.factura_interna.quincena_arribo_id IS
'FK a quincena_arribo (1-24). Dato de cabecera propagado desde PP. Para reportes y filtros';

-- Índices para performance en JOINs
CREATE INDEX IF NOT EXISTS idx_intencion_compra_quincena
ON public.intencion_compra(quincena_arribo_id);

CREATE INDEX IF NOT EXISTS idx_pedido_proveedor_quincena
ON public.pedido_proveedor(quincena_arribo_id);

CREATE INDEX IF NOT EXISTS idx_factura_interna_quincena
ON public.factura_interna(quincena_arribo_id);

-- [MIGRATION-097] Agregar quincena_arribo_id (dual-field strategy)
