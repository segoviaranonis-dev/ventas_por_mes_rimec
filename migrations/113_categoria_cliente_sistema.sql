-- ============================================================================
-- MIGRACIÓN 113: Sistema de Categorías de Cliente
-- ============================================================================
-- Fecha: 8 junio 2026
-- Objetivo: Sistema escalable de categorización para marcas
-- Alcance: Bazzar + Reports + Comparaciones + Cadena de clientes
-- Arquitectura: categoria_cliente → categoria_cliente_marca → tiendas_marcas
-- ============================================================================

-- ============================================================================
-- 1. TABLA MAESTRA: categoria_cliente
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.categoria_cliente (
  id SERIAL PRIMARY KEY,
  codigo VARCHAR(50) UNIQUE NOT NULL,
  descripcion TEXT NOT NULL,
  orden INT DEFAULT 0,
  activo BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insertar categorías base
INSERT INTO public.categoria_cliente (id, codigo, descripcion, orden) VALUES
  (1, 'ADULTOS', 'Productos para adultos (hombres y mujeres)', 1),
  (2, 'NINOS', 'Productos para niños (infantil)', 2),
  (3, 'ACCESORIOS', 'Accesorios y complementos', 3)
ON CONFLICT (codigo) DO NOTHING;

-- ============================================================================
-- 2. TABLA RELACIONAL: categoria_cliente_marca
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.categoria_cliente_marca (
  categoria_id INT NOT NULL,
  marca_id INT NOT NULL,
  activo BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (categoria_id, marca_id),
  FOREIGN KEY (categoria_id) REFERENCES public.categoria_cliente(id) ON DELETE CASCADE,
  FOREIGN KEY (marca_id) REFERENCES public.marca_v2(id_marca) ON DELETE CASCADE
);

-- ============================================================================
-- 3. POBLAR RELACIONES: Marcas por Categoría
-- ============================================================================

-- ADULTOS: Todas las marcas EXCEPTO Molekinha/Molekinho
INSERT INTO public.categoria_cliente_marca (categoria_id, marca_id)
SELECT 1, id_marca
FROM public.marca_v2
WHERE id_marca NOT IN (5, 6)  -- Excluir MOLEKINHA (5) y MOLEKINHO (6)
ON CONFLICT (categoria_id, marca_id) DO NOTHING;

-- NIÑOS: SOLO Molekinha y Molekinho
INSERT INTO public.categoria_cliente_marca (categoria_id, marca_id) VALUES
  (2, 5),  -- MOLEKINHA
  (2, 6)   -- MOLEKINHO
ON CONFLICT (categoria_id, marca_id) DO NOTHING;

-- ACCESORIOS: (vacío por ahora, futuro)
-- INSERT INTO categoria_cliente_marca (categoria_id, marca_id) VALUES (3, X);

-- ============================================================================
-- 4. ACTUALIZAR tiendas_marcas para usar categorías (REBUILD)
-- ============================================================================

-- Limpiar tabla tiendas_marcas existente
TRUNCATE TABLE public.tiendas_marcas;

-- Tiendas ADULTOS heredan de categoría ADULTOS (id=1)
INSERT INTO public.tiendas_marcas (cliente_id, marca_id)
SELECT cliente_id, marca_id
FROM (VALUES (2100), (2400), (3100)) AS tiendas_adultos(cliente_id)
CROSS JOIN public.categoria_cliente_marca ccm
WHERE ccm.categoria_id = 1  -- ADULTOS
  AND ccm.activo = true
ON CONFLICT (cliente_id, marca_id) DO NOTHING;

-- Tiendas NIÑOS heredan de categoría NIÑOS (id=2)
INSERT INTO public.tiendas_marcas (cliente_id, marca_id)
SELECT cliente_id, marca_id
FROM (VALUES (2900), (2700), (3200)) AS tiendas_ninos(cliente_id)
CROSS JOIN public.categoria_cliente_marca ccm
WHERE ccm.categoria_id = 2  -- NIÑOS
  AND ccm.activo = true
ON CONFLICT (cliente_id, marca_id) DO NOTHING;

-- ============================================================================
-- 5. ÍNDICES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_categoria_cliente_codigo
  ON public.categoria_cliente(codigo);

CREATE INDEX IF NOT EXISTS idx_categoria_cliente_marca_categoria
  ON public.categoria_cliente_marca(categoria_id);

CREATE INDEX IF NOT EXISTS idx_categoria_cliente_marca_marca
  ON public.categoria_cliente_marca(marca_id);

-- ============================================================================
-- 6. VISTAS HELPER
-- ============================================================================

-- Vista: Marcas por categoría con detalles
CREATE OR REPLACE VIEW public.v_categoria_marcas AS
SELECT
  cc.id AS categoria_id,
  cc.codigo AS categoria_codigo,
  cc.descripcion AS categoria,
  m.id_marca AS marca_id,
  m.descp_marca AS marca,
  ccm.activo
FROM public.categoria_cliente cc
INNER JOIN public.categoria_cliente_marca ccm ON ccm.categoria_id = cc.id
LEFT JOIN public.marca_v2 m ON m.id_marca = ccm.marca_id
WHERE cc.activo = true
ORDER BY cc.orden, m.descp_marca;

-- Vista: Tiendas con su categoría (derivada)
CREATE OR REPLACE VIEW public.v_tiendas_con_categoria AS
SELECT DISTINCT
  tm.cliente_id,
  CASE
    WHEN tm.cliente_id IN (2100, 2400, 3100) THEN 1  -- ADULTOS
    WHEN tm.cliente_id IN (2900, 2700, 3200) THEN 2  -- NIÑOS
  END AS categoria_id,
  CASE
    WHEN tm.cliente_id IN (2100, 2400, 3100) THEN 'ADULTOS'
    WHEN tm.cliente_id IN (2900, 2700, 3200) THEN 'NINOS'
  END AS categoria_codigo,
  CASE
    WHEN tm.cliente_id = 2100 THEN 'Fernando Adultos'
    WHEN tm.cliente_id = 2900 THEN 'Fernando Niños'
    WHEN tm.cliente_id = 2400 THEN 'San Martin Adultos'
    WHEN tm.cliente_id = 2700 THEN 'San Martin Niños'
    WHEN tm.cliente_id = 3100 THEN 'Palma Adultos'
    WHEN tm.cliente_id = 3200 THEN 'Palma Niños'
  END AS tienda_nombre
FROM public.tiendas_marcas tm;

-- Vista: Resumen de marcas por categoría
CREATE OR REPLACE VIEW public.v_resumen_categorias AS
SELECT
  cc.id,
  cc.codigo,
  cc.descripcion,
  COUNT(DISTINCT ccm.marca_id) AS total_marcas,
  string_agg(DISTINCT m.descp_marca, ', ' ORDER BY m.descp_marca) AS marcas_listado
FROM public.categoria_cliente cc
LEFT JOIN public.categoria_cliente_marca ccm ON ccm.categoria_id = cc.id AND ccm.activo = true
LEFT JOIN public.marca_v2 m ON m.id_marca = ccm.marca_id
WHERE cc.activo = true
GROUP BY cc.id, cc.codigo, cc.descripcion
ORDER BY cc.orden;

-- ============================================================================
-- 7. COMENTARIOS DOCUMENTACIÓN
-- ============================================================================

COMMENT ON TABLE public.categoria_cliente IS
  'Categorías maestras de cliente (ADULTOS, NIÑOS, ACCESORIOS). Sistema escalable para clasificar productos y tiendas.';

COMMENT ON TABLE public.categoria_cliente_marca IS
  'Relación N:N entre categorías y marcas. Define qué marcas pertenecen a cada categoría.';

COMMENT ON VIEW public.v_categoria_marcas IS
  'Lista todas las marcas por categoría con detalles completos.';

COMMENT ON VIEW public.v_tiendas_con_categoria IS
  'Deriva la categoría de cada tienda basándose en sus marcas asignadas.';

COMMENT ON VIEW public.v_resumen_categorias IS
  'Resumen ejecutivo: cuántas marcas tiene cada categoría.';

-- ============================================================================
-- 8. TRIGGER: Actualizar updated_at automáticamente
-- ============================================================================

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_categoria_cliente_updated_at
BEFORE UPDATE ON public.categoria_cliente
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- FIN MIGRACIÓN 113
-- ============================================================================
