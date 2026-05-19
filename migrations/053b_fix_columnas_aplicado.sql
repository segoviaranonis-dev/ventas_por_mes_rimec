-- ============================================================
-- MIGRACIÓN 053b — Fix columnas *_aplicado faltantes
-- ============================================================
-- OT: OT-HOTFIX-PELE-GKPJ-001
-- Fecha: 2026-05-18
-- Root cause: 053 no insertaba columnas *_aplicado; nombres deben coincidir con 004 (descuento_N_aplicado).
-- Intento 2 falló con: column "d1_aplicado" does not exist — corregido aquí.
-- ============================================================

BEGIN;

-- Columnas trazabilidad en precio_lista (idempotente; mismo esquema que 004)
ALTER TABLE public.precio_lista
    ADD COLUMN IF NOT EXISTS dolar_aplicado       NUMERIC,
    ADD COLUMN IF NOT EXISTS factor_aplicado      NUMERIC,
    ADD COLUMN IF NOT EXISTS indice_aplicado      NUMERIC,
    ADD COLUMN IF NOT EXISTS descuento_1_aplicado NUMERIC,
    ADD COLUMN IF NOT EXISTS descuento_2_aplicado NUMERIC,
    ADD COLUMN IF NOT EXISTS descuento_3_aplicado NUMERIC,
    ADD COLUMN IF NOT EXISTS descuento_4_aplicado NUMERIC,
    ADD COLUMN IF NOT EXISTS nombre_caso_aplicado TEXT;

COMMIT;

-- DROP función anterior (PostgreSQL no permite cambiar RETURNS TABLE)
DROP FUNCTION IF EXISTS calcular_precio_lista_evento_sql(bigint);

-- Crear función con columnas completas
CREATE OR REPLACE FUNCTION calcular_precio_lista_evento_sql(p_evento_id bigint)
RETURNS TABLE(total bigint, duracion_ms numeric, error text)
LANGUAGE plpgsql
AS $$
DECLARE
    v_start_time timestamptz;
    v_end_time   timestamptz;
    v_count      bigint;
BEGIN
    v_start_time := clock_timestamp();

    BEGIN
        WITH staging_con_caso AS (
            SELECT
                s.evento_id,
                s.caso_id,
                s.marca,
                s.linea_id,
                s.referencia_id,
                s.material_id,
                s.fob_fabrica,
                -- JOIN con caso para obtener parámetros
                c.dolar_politica,
                c.factor_conversion,
                c.descuento_1,
                c.descuento_2,
                c.descuento_3,
                c.descuento_4,
                c.genera_lpc03_lpc04,
                c.nombre_caso
            FROM precio_lista_staging s
            INNER JOIN precio_evento_caso c ON s.caso_id = c.id
            WHERE s.evento_id = p_evento_id
        ),
        calculado AS (
            SELECT
                evento_id,
                caso_id,
                marca,
                linea_id,
                referencia_id,
                material_id,
                fob_fabrica,
                dolar_politica,
                factor_conversion,
                descuento_1,
                descuento_2,
                descuento_3,
                descuento_4,
                nombre_caso,
                -- Cálculo fob_ajustado
                fob_fabrica
                    * COALESCE(1 - descuento_1, 1)
                    * COALESCE(1 - descuento_2, 1)
                    * COALESCE(1 - descuento_3, 1)
                    * COALESCE(1 - descuento_4, 1) AS fob_ajustado,
                -- Índice
                (dolar_politica * factor_conversion) / 100.0 AS indice,
                genera_lpc03_lpc04
            FROM staging_con_caso
        ),
        con_precios AS (
            SELECT
                evento_id,
                caso_id,
                marca,
                linea_id,
                referencia_id,
                material_id,
                fob_fabrica,
                fob_ajustado,
                indice,
                dolar_politica,
                factor_conversion,
                descuento_1,
                descuento_2,
                descuento_3,
                descuento_4,
                nombre_caso,
                -- LPN = FLOOR(fob_ajustado * indice / 100) * 100 (redondeo centena inferior)
                FLOOR(fob_ajustado * indice / 100.0) * 100 AS lpn,
                -- LPC03/LPC04 (solo si genera_lpc03_lpc04 = true)
                CASE
                    WHEN genera_lpc03_lpc04 THEN
                        FLOOR((FLOOR(fob_ajustado * indice / 100.0) * 100) * 1.12 / 100.0) * 100
                    ELSE NULL
                END AS lpc03,
                CASE
                    WHEN genera_lpc03_lpc04 THEN
                        FLOOR((FLOOR(fob_ajustado * indice / 100.0) * 100) * 1.20 / 100.0) * 100
                    ELSE NULL
                END AS lpc04
            FROM calculado
        )
        INSERT INTO precio_lista (
            evento_id,
            caso_id,
            marca,
            linea_id,
            referencia_id,
            material_id,
            fob_fabrica,
            fob_ajustado,
            lpn,
            lpc02,
            lpc03,
            lpc04,
            vigente,
            created_at,
            -- Columnas *_aplicado (nombres = migración 004 / Python guardar_precio_lista)
            dolar_aplicado,
            factor_aplicado,
            indice_aplicado,
            descuento_1_aplicado,
            descuento_2_aplicado,
            descuento_3_aplicado,
            descuento_4_aplicado,
            nombre_caso_aplicado
        )
        SELECT
            evento_id,
            caso_id,
            marca,
            linea_id,
            referencia_id,
            material_id,
            fob_fabrica,
            ROUND(fob_ajustado::numeric, 4), -- paridad con Python round(fob_ajustado, 4)
            lpn,
            NULL as lpc02, -- no calculado actualmente
            lpc03,
            lpc04,
            false, -- vigente se marca luego en Paso 4
            now(),
            -- Valores aplicados
            dolar_politica,
            factor_conversion,
            ROUND(indice::numeric, 6),
            descuento_1,
            descuento_2,
            descuento_3,
            descuento_4,
            nombre_caso
        FROM con_precios;

        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_end_time := clock_timestamp();

        RETURN QUERY SELECT
            v_count,
            EXTRACT(MILLISECONDS FROM (v_end_time - v_start_time)),
            NULL::text;

    EXCEPTION WHEN OTHERS THEN
        v_end_time := clock_timestamp();
        RETURN QUERY SELECT
            0::bigint,
            EXTRACT(MILLISECONDS FROM (v_end_time - v_start_time)),
            SQLERRM;
    END;
END;
$$;

-- Verificación
DO $$
BEGIN
  RAISE NOTICE 'Funcion calcular_precio_lista_evento_sql actualizada (053b)';
  RAISE NOTICE 'Ahora inserta columnas *_aplicado requeridas por NOT NULL';
END $$;
