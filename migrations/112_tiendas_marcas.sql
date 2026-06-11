-- ============================================================================
-- MIGRACIÓN 112: Tabla Relacional tiendas_marcas
-- ============================================================================
-- Fecha: 8 junio 2026
-- Objetivo: Definir qué marcas puede vender cada tienda
-- Regla: Adultos = TODAS excepto Molekinha/Molekinho
--        Niños = SOLO Molekinha/Molekinho
-- ============================================================================

-- Crear tabla relacional
CREATE TABLE IF NOT EXISTS public.tiendas_marcas (
  cliente_id INT NOT NULL,
  marca_id INT NOT NULL,
  activo BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (cliente_id, marca_id)
);

-- ============================================================================
-- POBLAR TABLA CON REGLAS DE NEGOCIO
-- ============================================================================

-- 1. FERNANDO ADULTOS (2100) - Todas las marcas EXCEPTO Molekinha/Molekinho
INSERT INTO public.tiendas_marcas (cliente_id, marca_id)
SELECT 2100, id_marca
FROM public.marca_v2
WHERE id_marca NOT IN (5, 6)  -- Excluir MOLEKINHA y MOLEKINHO
ON CONFLICT (cliente_id, marca_id) DO NOTHING;

-- 2. FERNANDO NIÑOS (2900) - SOLO Molekinha/Molekinho
INSERT INTO public.tiendas_marcas (cliente_id, marca_id) VALUES
  (2900, 5),  -- MOLEKINHA
  (2900, 6)   -- MOLEKINHO
ON CONFLICT (cliente_id, marca_id) DO NOTHING;

-- 3. SAN MARTIN ADULTOS (2400) - Todas las marcas EXCEPTO Molekinha/Molekinho
INSERT INTO public.tiendas_marcas (cliente_id, marca_id)
SELECT 2400, id_marca
FROM public.marca_v2
WHERE id_marca NOT IN (5, 6)
ON CONFLICT (cliente_id, marca_id) DO NOTHING;

-- 4. SAN MARTIN NIÑOS (2700) - SOLO Molekinha/Molekinho
INSERT INTO public.tiendas_marcas (cliente_id, marca_id) VALUES
  (2700, 5),  -- MOLEKINHA
  (2700, 6)   -- MOLEKINHO
ON CONFLICT (cliente_id, marca_id) DO NOTHING;

-- 5. PALMA ADULTOS (3100) - Todas las marcas EXCEPTO Molekinha/Molekinho
INSERT INTO public.tiendas_marcas (cliente_id, marca_id)
SELECT 3100, id_marca
FROM public.marca_v2
WHERE id_marca NOT IN (5, 6)
ON CONFLICT (cliente_id, marca_id) DO NOTHING;

-- 6. PALMA NIÑOS (3200) - SOLO Molekinha/Molekinho
INSERT INTO public.tiendas_marcas (cliente_id, marca_id) VALUES
  (3200, 5),  -- MOLEKINHA
  (3200, 6)   -- MOLEKINHO
ON CONFLICT (cliente_id, marca_id) DO NOTHING;

-- ============================================================================
-- ÍNDICES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_tiendas_marcas_cliente
  ON public.tiendas_marcas(cliente_id);

CREATE INDEX IF NOT EXISTS idx_tiendas_marcas_marca
  ON public.tiendas_marcas(marca_id);

-- ============================================================================
-- COMENTARIOS
-- ============================================================================

COMMENT ON TABLE public.tiendas_marcas IS
  'Define qué marcas puede vender cada tienda. Adultos = todas excepto Molekinha/Molekinho. Niños = solo Molekinha/Molekinho.';

COMMENT ON COLUMN public.tiendas_marcas.cliente_id IS
  'ID de la tienda (2100, 2900, 2400, 2700, 3100, 3200)';

COMMENT ON COLUMN public.tiendas_marcas.marca_id IS
  'ID de la marca permitida para esta tienda';

-- ============================================================================
-- VISTA HELPER: Marcas por tienda
-- ============================================================================

CREATE OR REPLACE VIEW public.v_tiendas_marcas_detalle AS
SELECT
  tm.cliente_id,
  CASE
    WHEN tm.cliente_id = 2100 THEN 'Fernando Adultos'
    WHEN tm.cliente_id = 2900 THEN 'Fernando Niños'
    WHEN tm.cliente_id = 2400 THEN 'San Martin Adultos'
    WHEN tm.cliente_id = 2700 THEN 'San Martin Niños'
    WHEN tm.cliente_id = 3100 THEN 'Palma Adultos'
    WHEN tm.cliente_id = 3200 THEN 'Palma Niños'
  END AS tienda,
  tm.marca_id,
  m.descp_marca AS marca,
  tm.activo
FROM public.tiendas_marcas tm
LEFT JOIN public.marca_v2 m ON m.id_marca = tm.marca_id
ORDER BY tm.cliente_id, m.descp_marca;

-- ============================================================================
-- FIN MIGRACIÓN 112
-- ============================================================================
