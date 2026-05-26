-- ============================================================================
-- MIGRACIÓN 096: Catálogo de Quincenas para Fecha de Arribo Estimada
-- AUTOR: Héctor & Claude AI
-- FECHA: 2026-05-26
-- DESCRIPCIÓN: Tabla maestra de quincenas (1-24) para estandarizar
--              fechas de arribo en importaciones
-- ============================================================================

-- Crear tabla de quincenas
CREATE TABLE IF NOT EXISTS public.quincena_arribo (
    id INTEGER PRIMARY KEY,
    descripcion TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Poblar con las 24 quincenas del año
INSERT INTO public.quincena_arribo (id, descripcion) VALUES
    (1,  '1ra Quincena de Enero'),
    (2,  '2da Quincena de Enero'),
    (3,  '1ra Quincena de Febrero'),
    (4,  '2da Quincena de Febrero'),
    (5,  '1ra Quincena de Marzo'),
    (6,  '2da Quincena de Marzo'),
    (7,  '1ra Quincena de Abril'),
    (8,  '2da Quincena de Abril'),
    (9,  '1ra Quincena de Mayo'),
    (10, '2da Quincena de Mayo'),
    (11, '1ra Quincena de Junio'),
    (12, '2da Quincena de Junio'),
    (13, '1ra Quincena de Julio'),
    (14, '2da Quincena de Julio'),
    (15, '1ra Quincena de Agosto'),
    (16, '2da Quincena de Agosto'),
    (17, '1ra Quincena de Septiembre'),
    (18, '2da Quincena de Septiembre'),
    (19, '1ra Quincena de Octubre'),
    (20, '2da Quincena de Octubre'),
    (21, '1ra Quincena de Noviembre'),
    (22, '2da Quincena de Noviembre'),
    (23, '1ra Quincena de Diciembre'),
    (24, '2da Quincena de Diciembre')
ON CONFLICT (id) DO NOTHING;

-- Comentarios
COMMENT ON TABLE public.quincena_arribo IS 'Catálogo maestro de quincenas (1-24) para fechas de arribo estimadas en importaciones';
COMMENT ON COLUMN public.quincena_arribo.id IS 'ID quincena: 1-24 (1=1ra Ene, 24=2da Dic)';
COMMENT ON COLUMN public.quincena_arribo.descripcion IS 'Descripción: "1ra Quincena de Enero", etc.';

-- [MIGRATION-096] Catálogo Quincena Arribo
