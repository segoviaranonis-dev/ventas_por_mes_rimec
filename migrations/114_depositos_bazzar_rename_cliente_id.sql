-- ============================================================================
-- MIGRACIÓN 114: Depósitos Bazzar — nomenclatura por cliente_id
-- ============================================================================
-- Reemplaza ente + adultos|ninos en el nombre de tabla por código cliente.
-- Patrón nuevo: deposito_{nivel}_{cliente_id}_{tienda|guardado|averiado}
-- OT: corrección nomenclatura Director 2026-06-17
-- ============================================================================

DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT * FROM (VALUES
      ('deposito_1_fernando_adultos_tienda',   'deposito_1_2100_tienda'),
      ('deposito_2_fernando_adultos_guardado',  'deposito_2_2100_guardado'),
      ('deposito_3_fernando_adultos_averiado', 'deposito_3_2100_averiado'),
      ('deposito_1_fernando_ninos_tienda',     'deposito_1_2900_tienda'),
      ('deposito_2_fernando_ninos_guardado',   'deposito_2_2900_guardado'),
      ('deposito_3_fernando_ninos_averiado',   'deposito_3_2900_averiado'),
      ('deposito_1_sanmartin_adultos_tienda',   'deposito_1_2400_tienda'),
      ('deposito_2_sanmartin_adultos_guardado',  'deposito_2_2400_guardado'),
      ('deposito_3_sanmartin_adultos_averiado', 'deposito_3_2400_averiado'),
      ('deposito_1_sanmartin_ninos_tienda',     'deposito_1_2700_tienda'),
      ('deposito_2_sanmartin_ninos_guardado',   'deposito_2_2700_guardado'),
      ('deposito_3_sanmartin_ninos_averiado',   'deposito_3_2700_averiado'),
      ('deposito_1_palma_adultos_tienda',   'deposito_1_3100_tienda'),
      ('deposito_2_palma_adultos_guardado',  'deposito_2_3100_guardado'),
      ('deposito_3_palma_adultos_averiado', 'deposito_3_3100_averiado'),
      ('deposito_1_palma_ninos_tienda',     'deposito_1_3200_tienda'),
      ('deposito_2_palma_ninos_guardado',   'deposito_2_3200_guardado'),
      ('deposito_3_palma_ninos_averiado',   'deposito_3_3200_averiado')
    ) AS t(old_name, new_name)
  LOOP
    IF to_regclass('public.' || r.old_name) IS NOT NULL
       AND to_regclass('public.' || r.new_name) IS NULL THEN
      EXECUTE format('ALTER TABLE public.%I RENAME TO %I', r.old_name, r.new_name);
      RAISE NOTICE 'Renamed % -> %', r.old_name, r.new_name;
    ELSIF to_regclass('public.' || r.new_name) IS NOT NULL THEN
      RAISE NOTICE 'Skip (ya existe): %', r.new_name;
    END IF;
  END LOOP;
END $$;

COMMENT ON TABLE public.deposito_1_2100_tienda IS 'Bazzar cliente_id 2100 · Fernando Adultos · stock piso tienda';
COMMENT ON TABLE public.deposito_2_2100_guardado IS 'Bazzar cliente_id 2100 · Fernando Adultos · guardado';
COMMENT ON TABLE public.deposito_3_2100_averiado IS 'Bazzar cliente_id 2100 · Fernando Adultos · averiado';
COMMENT ON TABLE public.deposito_1_2900_tienda IS 'Bazzar cliente_id 2900 · Fernando Niños · stock piso tienda';
COMMENT ON TABLE public.deposito_2_2900_guardado IS 'Bazzar cliente_id 2900 · Fernando Niños · guardado';
COMMENT ON TABLE public.deposito_3_2900_averiado IS 'Bazzar cliente_id 2900 · Fernando Niños · averiado';
COMMENT ON TABLE public.deposito_1_2400_tienda IS 'Bazzar cliente_id 2400 · San Martin Adultos · tienda';
COMMENT ON TABLE public.deposito_1_2700_tienda IS 'Bazzar cliente_id 2700 · San Martin Niños · tienda';
COMMENT ON TABLE public.deposito_1_3100_tienda IS 'Bazzar cliente_id 3100 · Palma Adultos · tienda';
COMMENT ON TABLE public.deposito_1_3200_tienda IS 'Bazzar cliente_id 3200 · Palma Niños · tienda';

-- ============================================================================
-- FIN MIGRACIÓN 114
-- ============================================================================
