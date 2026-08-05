-- MIG-145 — Excepción PROMOCIONAL: LPC03 = LPN (Director · 2026-07-07)
-- Caso promocional no genera +12%; clientes con política LPC03 deben ver precio = LPN.

-- Backfill precio_lista existente
UPDATE precio_lista pl
SET lpc03 = pl.lpn
WHERE pl.lpc03 IS NULL
  AND pl.lpn IS NOT NULL
  AND pl.lpn > 0
  AND UPPER(TRIM(COALESCE(pl.nombre_caso_aplicado, ''))) = 'PROMOCIONAL';

-- Backfill snapshot PPD (catálogo v_stock_rimec cuando usa columnas PPD)
UPDATE pedido_proveedor_detalle ppd
SET precio_lpc03 = ppd.precio_lpn
WHERE ppd.precio_lpc03 IS NULL
  AND ppd.precio_lpn IS NOT NULL
  AND ppd.precio_lpn > 0
  AND UPPER(TRIM(COALESCE(ppd.descp_caso_snapshot, ''))) = 'PROMOCIONAL';

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
                fob_fabrica
                    * COALESCE(1 - descuento_1, 1)
                    * COALESCE(1 - descuento_2, 1)
                    * COALESCE(1 - descuento_3, 1)
                    * COALESCE(1 - descuento_4, 1) AS fob_ajustado,
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
                FLOOR(fob_ajustado * indice / 100.0) * 100 AS lpn,
                CASE
                    WHEN genera_lpc03_lpc04 THEN
                        FLOOR((FLOOR(fob_ajustado * indice / 100.0) * 100) * 1.12 / 100.0) * 100
                    WHEN UPPER(TRIM(COALESCE(nombre_caso, ''))) = 'PROMOCIONAL' THEN
                        FLOOR(fob_ajustado * indice / 100.0) * 100
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
            dolar_aplicado,
            factor_aplicado,
            indice_aplicado,
            descuento_1_aplicado,
            descuento_2_aplicado,
            descuento_3_aplicado,
            descuento_4_aplicado,
            nombre_caso_aplicado,
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
            NULL,
            lpc03,
            lpc04,
            false,
            now(),
            dolar_politica,
            factor_conversion,
            ROUND(indice::numeric, 6),
            descuento_1,
            descuento_2,
            descuento_3,
            descuento_4,
            nombre_caso,
            linea_codigo,
            ref_codigo,
            material_desc
        FROM con_precios;

        GET DIAGNOSTICS v_count = ROW_COUNT;
        v_end_time := clock_timestamp();

        RETURN QUERY SELECT v_count, EXTRACT(EPOCH FROM (v_end_time - v_start_time)) * 1000, NULL::text;

    EXCEPTION WHEN OTHERS THEN
        v_end_time := clock_timestamp();
        RETURN QUERY SELECT 0::bigint, EXTRACT(EPOCH FROM (v_end_time - v_start_time)) * 1000, SQLERRM;
    END;
END;
$$;
