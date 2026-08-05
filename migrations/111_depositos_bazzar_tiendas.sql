-- ============================================================================
-- MIGRACIÓN 111: Depósitos Bazzar - 6 Tiendas
-- ============================================================================
-- Fecha: 8 junio 2026
-- Objetivo: Crear 6 tablas de depósito para Venta en Tienda (POS tablet)
-- Estructura: Copia de registro_st_vt_rc_reposicion (solo stock)
-- ETL: Sincronización diaria desde registro_st_vt_rc_reposicion por cliente_id
-- ============================================================================

-- FERNANDO ADULTOS (cliente_id = 2100)
CREATE TABLE IF NOT EXISTS public.deposito_2_fernando_adultos_tienda (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);

-- FERNANDO NIÑOS (cliente_id = 2900)
CREATE TABLE IF NOT EXISTS public.deposito_2_fernando_ninos_tienda (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);

-- SAN MARTIN ADULTOS (cliente_id = 2400)
CREATE TABLE IF NOT EXISTS public.deposito_3_sanmartin_adultos_tienda (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);

-- SAN MARTIN NIÑOS (cliente_id = 2700)
CREATE TABLE IF NOT EXISTS public.deposito_3_sanmartin_ninos_tienda (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);

-- PALMA ADULTOS (cliente_id = 3100)
CREATE TABLE IF NOT EXISTS public.deposito_1_palma_adultos_tienda (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);

-- PALMA NIÑOS (cliente_id = 3200)
CREATE TABLE IF NOT EXISTS public.deposito_1_palma_ninos_tienda (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);

-- ============================================================================
-- ÍNDICES PARA PERFORMANCE
-- ============================================================================

-- Fernando Adultos
CREATE INDEX IF NOT EXISTS idx_dep_fernando_adultos_cliente
  ON public.deposito_2_fernando_adultos_tienda(cliente_id);
CREATE INDEX IF NOT EXISTS idx_dep_fernando_adultos_linea_ref
  ON public.deposito_2_fernando_adultos_tienda(linea_id, referencia_id);
CREATE INDEX IF NOT EXISTS idx_dep_fernando_adultos_material_color
  ON public.deposito_2_fernando_adultos_tienda(material_id, color_id);

-- Fernando Niños
CREATE INDEX IF NOT EXISTS idx_dep_fernando_ninos_cliente
  ON public.deposito_2_fernando_ninos_tienda(cliente_id);
CREATE INDEX IF NOT EXISTS idx_dep_fernando_ninos_linea_ref
  ON public.deposito_2_fernando_ninos_tienda(linea_id, referencia_id);
CREATE INDEX IF NOT EXISTS idx_dep_fernando_ninos_material_color
  ON public.deposito_2_fernando_ninos_tienda(material_id, color_id);

-- San Martin Adultos
CREATE INDEX IF NOT EXISTS idx_dep_sanmartin_adultos_cliente
  ON public.deposito_3_sanmartin_adultos_tienda(cliente_id);
CREATE INDEX IF NOT EXISTS idx_dep_sanmartin_adultos_linea_ref
  ON public.deposito_3_sanmartin_adultos_tienda(linea_id, referencia_id);
CREATE INDEX IF NOT EXISTS idx_dep_sanmartin_adultos_material_color
  ON public.deposito_3_sanmartin_adultos_tienda(material_id, color_id);

-- San Martin Niños
CREATE INDEX IF NOT EXISTS idx_dep_sanmartin_ninos_cliente
  ON public.deposito_3_sanmartin_ninos_tienda(cliente_id);
CREATE INDEX IF NOT EXISTS idx_dep_sanmartin_ninos_linea_ref
  ON public.deposito_3_sanmartin_ninos_tienda(linea_id, referencia_id);
CREATE INDEX IF NOT EXISTS idx_dep_sanmartin_ninos_material_color
  ON public.deposito_3_sanmartin_ninos_tienda(material_id, color_id);

-- Palma Adultos
CREATE INDEX IF NOT EXISTS idx_dep_palma_adultos_cliente
  ON public.deposito_1_palma_adultos_tienda(cliente_id);
CREATE INDEX IF NOT EXISTS idx_dep_palma_adultos_linea_ref
  ON public.deposito_1_palma_adultos_tienda(linea_id, referencia_id);
CREATE INDEX IF NOT EXISTS idx_dep_palma_adultos_material_color
  ON public.deposito_1_palma_adultos_tienda(material_id, color_id);

-- Palma Niños
CREATE INDEX IF NOT EXISTS idx_dep_palma_ninos_cliente
  ON public.deposito_1_palma_ninos_tienda(cliente_id);
CREATE INDEX IF NOT EXISTS idx_dep_palma_ninos_linea_ref
  ON public.deposito_1_palma_ninos_tienda(linea_id, referencia_id);
CREATE INDEX IF NOT EXISTS idx_dep_palma_ninos_material_color
  ON public.deposito_1_palma_ninos_tienda(material_id, color_id);

-- ============================================================================
-- COMENTARIOS PARA DOCUMENTACIÓN
-- ============================================================================

COMMENT ON TABLE public.deposito_2_fernando_adultos_tienda IS
  'Depósito Bazzar Fernando Adultos (cliente_id 2100) - Sincronizado diariamente desde registro_st_vt_rc_reposicion';

COMMENT ON TABLE public.deposito_2_fernando_ninos_tienda IS
  'Depósito Bazzar Fernando Niños (cliente_id 2900) - Solo marcas Molekinha/Molekinho';

COMMENT ON TABLE public.deposito_3_sanmartin_adultos_tienda IS
  'Depósito Bazzar San Martin Adultos (cliente_id 2400) - Sincronizado diariamente desde registro_st_vt_rc_reposicion';

COMMENT ON TABLE public.deposito_3_sanmartin_ninos_tienda IS
  'Depósito Bazzar San Martin Niños (cliente_id 2700) - Solo marcas Molekinha/Molekinho';

COMMENT ON TABLE public.deposito_1_palma_adultos_tienda IS
  'Depósito Bazzar Palma Adultos (cliente_id 3100) - Sincronizado diariamente desde registro_st_vt_rc_reposicion';

COMMENT ON TABLE public.deposito_1_palma_ninos_tienda IS
  'Depósito Bazzar Palma Niños (cliente_id 3200) - Solo marcas Molekinha/Molekinho';

-- ============================================================================
-- FIN MIGRACIÓN 111
-- ============================================================================
