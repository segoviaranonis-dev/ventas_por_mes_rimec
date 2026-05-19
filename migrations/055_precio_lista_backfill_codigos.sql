-- ============================================================
-- MIGRACIÓN 055 — Backfill códigos denormalizados en precio_lista
-- ============================================================
-- Fecha: 2026-05-19
-- Root cause: 053b INSERT SQL no poblaba linea_codigo/referencia_codigo/material_descripcion
-- Síntoma: PP explorador muestra "—" en columnas Línea/Ref porque JOIN por códigos falla
-- Fix: Backfill desde FK + actualizar función 053b para poblar en futuros cálculos
-- ============================================================

-- Paso 1: Backfill filas existentes con códigos NULL
UPDATE precio_lista pl
SET
    linea_codigo = l.codigo_proveedor::text,
    referencia_codigo = r.codigo_proveedor::text,
    material_descripcion = m.descripcion
FROM linea l, referencia r, material m
WHERE pl.linea_id = l.id
  AND pl.referencia_id = r.id
  AND pl.material_id = m.id
  AND (pl.linea_codigo IS NULL OR pl.referencia_codigo IS NULL OR pl.material_descripcion IS NULL);

-- Verificación: contar filas actualizadas
DO $$
DECLARE
    v_count_sin_codigo integer;
BEGIN
    SELECT COUNT(*) INTO v_count_sin_codigo
    FROM precio_lista
    WHERE linea_codigo IS NULL OR referencia_codigo IS NULL;

    IF v_count_sin_codigo > 0 THEN
        RAISE WARNING 'Quedan % filas en precio_lista sin códigos denormalizados (posible FK huérfano)', v_count_sin_codigo;
    ELSE
        RAISE NOTICE 'Backfill completado — todas las filas tienen códigos denormalizados';
    END IF;
END $$;

-- Paso 2: Actualizar función 053b para insertar códigos en futuros cálculos
DROP FUNCTION IF EXISTS calcular_precio_lista_evento_sql(bigint);

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
                s.linea_codigo,
                s.ref_codigo,
                s.material_desc,
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
                linea_codigo,
                ref_codigo,
                material_desc,
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
                linea_codigo,
                ref_codigo,
                material_desc,
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
            -- Columnas *_aplicado (053b)
            dolar_aplicado,
            factor_aplicado,
            indice_aplicado,
            d1_aplicado,
            d2_aplicado,
            d3_aplicado,
            d4_aplicado,
            nombre_caso_aplicado,
            -- Códigos denormalizados (055)
            linea_codigo,
            referencia_codigo,
            material_descripcion
        )
        SELECT
            evento_id,
            caso_id,
            marca,
            linea_id,
            referencia_id,
            material_id,
            fob_fabrica,
            ROUND(fob_ajustado::numeric, 4),
            lpn,
            NULL as lpc02,
            lpc03,
            lpc04,
            false,
            now(),
            -- Valores aplicados
            dolar_politica,
            factor_conversion,
            ROUND(indice::numeric, 6),
            descuento_1,
            descuento_2,
            descuento_3,
            descuento_4,
            nombre_caso,
            -- Códigos denormalizados desde staging
            linea_codigo,
            ref_codigo,
            material_desc
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

-- Verificación final
DO $$
BEGIN
  RAISE NOTICE 'Migración 055 completada:';
  RAISE NOTICE '  - Backfill códigos denormalizados en precio_lista';
  RAISE NOTICE '  - Función calcular_precio_lista_evento_sql actualizada con códigos';
END $$;
