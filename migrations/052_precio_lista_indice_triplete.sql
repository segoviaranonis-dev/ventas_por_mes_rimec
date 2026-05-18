-- ============================================================
-- MIGRACIÓN 052 — Índice triplete + evento para precio_lista
-- ============================================================
-- OT: OT-MOTOR-SQL-520-001
-- Fecha: 2026-05-18
-- Objetivo: Optimizar lookup PP/FI y cálculo masivo por evento
--
-- Índice triplete (evento_id, linea_id, referencia_id, material_id)
-- permite O(log n) en JOINs y queries de precio sugerido.
-- ============================================================

-- Índice principal para lookup PP/FI y cálculo por evento
CREATE INDEX IF NOT EXISTS idx_precio_lista_evento_triplete
  ON public.precio_lista (evento_id, linea_id, referencia_id, material_id);

-- Índice adicional para queries que filtran por vigente
-- (útil para consultas de precio sugerido en PP/FI activos)
CREATE INDEX IF NOT EXISTS idx_precio_lista_evento_vigente_triplete
  ON public.precio_lista (evento_id, linea_id, referencia_id, material_id)
  WHERE vigente = true;

-- Verificación
DO $$
BEGIN
  RAISE NOTICE 'Índices triplete creados en precio_lista';
  RAISE NOTICE 'idx_precio_lista_evento_triplete: evento_id, linea_id, referencia_id, material_id';
  RAISE NOTICE 'idx_precio_lista_evento_vigente_triplete: igual + WHERE vigente = true';
END $$;
