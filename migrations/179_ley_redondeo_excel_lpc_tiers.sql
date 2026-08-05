-- MIG-179 — Ley redondeo Excel LPC03/LPC04 (Director · 2026-07-25)
-- Un solo ROUND centena sobre base bruta (FOB×índice)×factor — paridad Excel manual 7200.
-- PROMOCIONAL: LPC03 = LPC04 = LPN.

BEGIN;

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
                public.redondear_centena_gs(fob_ajustado * indice) AS lpn,
                CASE
                    WHEN genera_lpc03_lpc04 THEN
                        public.redondear_centena_gs(fob_ajustado * indice * 1.12)
                    WHEN UPPER(TRIM(COALESCE(nombre_caso, ''))) = 'PROMOCIONAL' THEN
                        public.redondear_centena_gs(fob_ajustado * indice)
                    ELSE NULL
                END AS lpc03,
                CASE
                    WHEN genera_lpc03_lpc04 THEN
                        public.redondear_centena_gs(fob_ajustado * indice * 1.20)
                    WHEN UPPER(TRIM(COALESCE(nombre_caso, ''))) = 'PROMOCIONAL' THEN
                        public.redondear_centena_gs(fob_ajustado * indice)
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

CREATE OR REPLACE FUNCTION public.fn_precio_tier_vista(
  p_lista integer,
  p_lpn numeric,
  p_lpc02 numeric,
  p_lpc03 numeric,
  p_lpc04 numeric,
  p_descp_caso text
)
RETURNS numeric
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT CASE p_lista
    WHEN 1 THEN public.redondear_centena_gs(p_lpn)
    WHEN 2 THEN public.redondear_centena_gs(p_lpc02)
    WHEN 3 THEN
      CASE
        WHEN UPPER(TRIM(COALESCE(p_descp_caso, ''))) = 'PROMOCIONAL' THEN
          public.redondear_centena_gs(p_lpn)
        WHEN COALESCE(p_lpc03, 0) > 0 THEN
          public.redondear_centena_gs(p_lpc03)
        WHEN COALESCE(p_lpn, 0) > 0 THEN
          public.redondear_centena_gs(p_lpn * 1.12)
        ELSE 0
      END
    WHEN 4 THEN
      CASE
        WHEN UPPER(TRIM(COALESCE(p_descp_caso, ''))) = 'PROMOCIONAL' THEN
          public.redondear_centena_gs(p_lpn)
        WHEN COALESCE(p_lpc04, 0) > 0 THEN
          public.redondear_centena_gs(p_lpc04)
        WHEN COALESCE(p_lpn, 0) > 0 THEN
          public.redondear_centena_gs(p_lpn * 1.20)
        ELSE 0
      END
    ELSE public.redondear_centena_gs(p_lpn)
  END;
$$;

COMMENT ON FUNCTION public.fn_precio_tier_vista(integer, numeric, numeric, numeric, numeric, text) IS
  'MIG-179: tier Excel · LPC desde snapshot · PROMO=LPN.';

CREATE OR REPLACE FUNCTION public.apply_ley_precios_rimec_web_ppd(
  p_pp_id bigint DEFAULT NULL
)
RETURNS TABLE(filas_actualizadas bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  n_promo bigint := 0;
BEGIN
  UPDATE public.pedido_proveedor_detalle ppd
  SET
    precio_lpc03 = public.redondear_centena_gs(ppd.precio_lpn),
    precio_lpc04 = public.redondear_centena_gs(ppd.precio_lpn)
  WHERE ppd.precio_lpn IS NOT NULL
    AND ppd.precio_lpn > 0
    AND (p_pp_id IS NULL OR ppd.pedido_proveedor_id = p_pp_id)
    AND UPPER(TRIM(COALESCE(ppd.descp_caso_snapshot, ''))) = 'PROMOCIONAL';

  GET DIAGNOSTICS n_promo = ROW_COUNT;

  filas_actualizadas := n_promo;
  RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.apply_ley_precios_rimec_web_ppd(bigint) IS
  'MIG-179: solo PROMO LPN=LPC03=LPC04. Normal: precios desde precio_lista al vincular.';

COMMIT;

SELECT 'MIG-179 OK: ley redondeo Excel LPC tiers' AS estado;
