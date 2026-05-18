-- ============================================================
-- MIGRACIÓN 053 — Función cálculo masivo precio_lista
-- ============================================================
-- OT: OT-MOTOR-SQL-520-001
-- Fecha: 2026-05-18
-- Objetivo: Cálculo set-based SQL para precio_lista (paridad con Python)
--
-- IMPORTANTE: Esta función asume que existe una tabla staging
-- precio_lista_staging con SKUs ya mapeados a casos.
-- ============================================================

-- Tabla staging para cálculo masivo
CREATE TABLE IF NOT EXISTS precio_lista_staging (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evento_id      bigint  NOT NULL,
    caso_id        bigint  NOT NULL,
    marca          text    NOT NULL,
    linea_id       bigint  NOT NULL,
    referencia_id  bigint  NOT NULL,
    material_id    bigint  NOT NULL,
    fob_fabrica    numeric NOT NULL,
    -- Códigos denormalizados para auditoría
    linea_codigo   text    NULL,
    ref_codigo     text    NULL,
    material_desc  text    NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- Índices para staging (optimizar JOINs)
CREATE INDEX IF NOT EXISTS idx_precio_lista_staging_evento_caso
  ON precio_lista_staging(evento_id, caso_id);

-- ============================================================
-- FUNCIÓN: calcular_precio_lista_evento_sql
-- ============================================================
-- Toma SKUs de precio_lista_staging, aplica fórmula caso,
-- inserta masivamente en precio_lista.
--
-- Paridad con calcular_precios_caso() en logic.py:
--   fob_ajustado = fob × (1-d1)×(1-d2)×(1-d3)×(1-d4)
--   indice = (dolar_politica * factor_conversion) / 100
--   lpn = FLOOR(fob_ajustado * indice / 100) * 100
--   lpc03 = FLOOR(lpn * 1.12 / 100) * 100 (si genera_lpc03_lpc04)
--   lpc04 = FLOOR(lpn * 1.20 / 100) * 100 (si genera_lpc03_lpc04)
-- ============================================================

CREATE OR REPLACE FUNCTION calcular_precio_lista_evento_sql(
    p_evento_id bigint
)
RETURNS TABLE(
    total_insertados bigint,
    duracion_ms numeric
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_start_time timestamptz;
    v_end_time   timestamptz;
    v_count      bigint;
BEGIN
    v_start_time := clock_timestamp();

    -- Validar que el evento existe
    IF NOT EXISTS (SELECT 1 FROM precio_evento WHERE id = p_evento_id) THEN
        RAISE EXCEPTION 'Evento % no existe', p_evento_id;
    END IF;

    -- Calcular e insertar masivamente
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
            c.genera_lpc03_lpc04
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
        created_at
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
        now()
    FROM con_precios;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_end_time := clock_timestamp();

    RETURN QUERY
    SELECT
        v_count,
        EXTRACT(MILLISECONDS FROM (v_end_time - v_start_time))::numeric;
END;
$$;

-- Verificación
DO $$
BEGIN
  RAISE NOTICE 'Función calcular_precio_lista_evento_sql creada';
  RAISE NOTICE 'Tabla precio_lista_staging creada';
  RAISE NOTICE 'Uso: SELECT * FROM calcular_precio_lista_evento_sql(<evento_id>)';
END $$;
