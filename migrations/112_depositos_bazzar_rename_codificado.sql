-- ============================================================================
-- MIGRACIÓN 112: Renombrar depósitos Bazzar — nomenclatura codificada (DEFINITIVO)
-- ============================================================================
-- Patrón: deposito_{N}_{ubicacion}_{adultos|ninos}_tienda
-- Palma=1 · Fernando=2 · San Martin=3
-- Idempotente: solo renombra si existe el nombre legacy.
-- ============================================================================

DO $$
BEGIN
  IF to_regclass('public.deposito_tienda_palma_adultos') IS NOT NULL THEN
    ALTER TABLE public.deposito_tienda_palma_adultos RENAME TO deposito_1_palma_adultos_tienda;
  END IF;
  IF to_regclass('public.deposito_tienda_palma_ninos') IS NOT NULL THEN
    ALTER TABLE public.deposito_tienda_palma_ninos RENAME TO deposito_1_palma_ninos_tienda;
  END IF;
  IF to_regclass('public.deposito_tienda_fernando_adultos') IS NOT NULL THEN
    ALTER TABLE public.deposito_tienda_fernando_adultos RENAME TO deposito_2_fernando_adultos_tienda;
  END IF;
  IF to_regclass('public.deposito_tienda_fernando_ninos') IS NOT NULL THEN
    ALTER TABLE public.deposito_tienda_fernando_ninos RENAME TO deposito_2_fernando_ninos_tienda;
  END IF;
  IF to_regclass('public.deposito_tienda_sanmartin_adultos') IS NOT NULL THEN
    ALTER TABLE public.deposito_tienda_sanmartin_adultos RENAME TO deposito_3_sanmartin_adultos_tienda;
  END IF;
  IF to_regclass('public.deposito_tienda_sanmartin_ninos') IS NOT NULL THEN
    ALTER TABLE public.deposito_tienda_sanmartin_ninos RENAME TO deposito_3_sanmartin_ninos_tienda;
  END IF;
END $$;
