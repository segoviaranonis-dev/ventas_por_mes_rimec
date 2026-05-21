-- ============================================================
-- MIGRACIÓN 053 — Tabla staging para cálculo masivo precio_lista
-- ============================================================
-- OT: OT-MOTOR-SQL-520-001
-- Fecha: 2026-05-18
--
-- La función calcular_precio_lista_evento_sql vive en 053b (3 columnas:
-- total, duracion_ms, error + columnas descuento_*_aplicado).
-- NO pegar aquí CREATE FUNCTION si ya aplicaste 053b (error 42P13).
-- ============================================================

CREATE TABLE IF NOT EXISTS precio_lista_staging (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evento_id      bigint  NOT NULL,
    caso_id        bigint  NOT NULL,
    marca          text    NOT NULL,
    linea_id       bigint  NOT NULL,
    referencia_id  bigint  NOT NULL,
    material_id    bigint  NOT NULL,
    fob_fabrica    numeric NOT NULL,
    linea_codigo   text    NULL,
    ref_codigo     text    NULL,
    material_desc  text    NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_precio_lista_staging_evento_caso
  ON precio_lista_staging(evento_id, caso_id);

DO $$
BEGIN
  RAISE NOTICE '053 OK: precio_lista_staging + índice (función = migración 053b)';
END $$;
