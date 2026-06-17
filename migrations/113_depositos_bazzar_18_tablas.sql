-- ============================================================================
-- MIGRACIÓN 113: Nomenclatura definitiva 18 depósitos Bazzar
-- ============================================================================
-- Patrón: deposito_{nivel}_{ente}_{adultos|ninos}_{tienda|guardado|averiado}
--   nivel 1 = tienda · nivel 2 = guardado · nivel 3 = averiado
-- 6 tiendas × 3 categorías = 18 tablas
-- ============================================================================

-- Corregir tienda: Fernando y San Martin → prefijo deposito_1_
DO $$
BEGIN
  IF to_regclass('public.deposito_2_fernando_adultos_tienda') IS NOT NULL THEN
    ALTER TABLE public.deposito_2_fernando_adultos_tienda RENAME TO deposito_1_fernando_adultos_tienda;
  END IF;
  IF to_regclass('public.deposito_2_fernando_ninos_tienda') IS NOT NULL THEN
    ALTER TABLE public.deposito_2_fernando_ninos_tienda RENAME TO deposito_1_fernando_ninos_tienda;
  END IF;
  IF to_regclass('public.deposito_3_sanmartin_adultos_tienda') IS NOT NULL THEN
    ALTER TABLE public.deposito_3_sanmartin_adultos_tienda RENAME TO deposito_1_sanmartin_adultos_tienda;
  END IF;
  IF to_regclass('public.deposito_3_sanmartin_ninos_tienda') IS NOT NULL THEN
    ALTER TABLE public.deposito_3_sanmartin_ninos_tienda RENAME TO deposito_1_sanmartin_ninos_tienda;
  END IF;
END $$;

-- Guardado (nivel 2) — 6 tablas
CREATE TABLE IF NOT EXISTS public.deposito_2_fernando_adultos_guardado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_2_fernando_ninos_guardado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_2_sanmartin_adultos_guardado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_2_sanmartin_ninos_guardado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_2_palma_adultos_guardado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_2_palma_ninos_guardado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);

-- Averiado (nivel 3) — 6 tablas
CREATE TABLE IF NOT EXISTS public.deposito_3_fernando_adultos_averiado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_3_fernando_ninos_averiado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_3_sanmartin_adultos_averiado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_3_sanmartin_ninos_averiado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_3_palma_adultos_averiado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);
CREATE TABLE IF NOT EXISTS public.deposito_3_palma_ninos_averiado (
  LIKE public.registro_st_vt_rc_reposicion INCLUDING ALL
);

COMMENT ON TABLE public.deposito_1_fernando_adultos_tienda IS 'Bazzar FER-A · cliente_id 2100 · stock piso tienda';
COMMENT ON TABLE public.deposito_2_fernando_adultos_guardado IS 'Bazzar FER-A · cliente_id 2100 · guardado';
COMMENT ON TABLE public.deposito_3_fernando_adultos_averiado IS 'Bazzar FER-A · cliente_id 2100 · averiado';
