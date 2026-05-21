-- Migración 057: Tabla ETA catálogo (fechas de arribo normalizadas)
-- OT: OT-RIMEC-WEB-TARJETAS-MULTI-ORIGEN-001
-- Autor: Claude Code
-- Fecha: 2026-05-19
--
-- Objetivo: Normalizar fechas ETA como entidad para agrupación de tarjetas TRÁNSITO.
-- Cada ETA única → fila en catálogo → agrupación SQL de tarjetas con mismo origen.

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 1: Crear tabla eta_catalogo
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS eta_catalogo (
  id                BIGSERIAL PRIMARY KEY,
  fecha_arribo      DATE NOT NULL UNIQUE,
  label_corto       TEXT,                    -- "15-06" formato DD-MM para UI
  quincena_hash     INTEGER,                 -- Hash para selección de paleta frontend
  descripcion       TEXT,                    -- Descripción opcional (ej. "Arribo junio 2025")
  activo            BOOLEAN DEFAULT true,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW(),

  CONSTRAINT eta_catalogo_fecha_valida CHECK (fecha_arribo >= '2020-01-01' AND fecha_arribo <= '2030-12-31')
);

CREATE INDEX idx_eta_catalogo_fecha ON eta_catalogo(fecha_arribo) WHERE activo = true;
CREATE INDEX idx_eta_catalogo_activo ON eta_catalogo(activo);

COMMENT ON TABLE eta_catalogo IS 'Catálogo de fechas ETA (arribo estimado PP). Fuente única de verdad para agrupación de tarjetas TRÁNSITO en web.';
COMMENT ON COLUMN eta_catalogo.fecha_arribo IS 'Fecha ISO YYYY-MM-DD del arribo estimado del pedido proveedor.';
COMMENT ON COLUMN eta_catalogo.label_corto IS 'Label UI corto: DD-MM (ej. "15-06"). Generado automáticamente.';
COMMENT ON COLUMN eta_catalogo.quincena_hash IS 'Hash numérico para rotación de paleta de colores frontend (celeste/naranja/violeta/verde).';

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 2: Función para generar label_corto automáticamente
-- ══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION generar_eta_label_corto(p_fecha DATE)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
  RETURN TO_CHAR(p_fecha, 'DD-MM');
END;
$$;

COMMENT ON FUNCTION generar_eta_label_corto IS 'Genera label corto DD-MM desde fecha ISO para display en tarjetas web.';

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 3: Función para calcular hash de quincena (paleta frontend)
-- ══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION calcular_quincena_hash(p_fecha DATE)
RETURNS INTEGER
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  v_fecha_str TEXT;
  v_hash BIGINT := 0;
  v_char TEXT;
  v_i INTEGER;
BEGIN
  v_fecha_str := p_fecha::TEXT;

  FOR v_i IN 1..LENGTH(v_fecha_str) LOOP
    v_char := SUBSTRING(v_fecha_str FROM v_i FOR 1);
    v_hash := ((v_hash * 31) + ASCII(v_char)) & 2147483647;  -- Mod 2^31 para evitar overflow
  END LOOP;

  RETURN ABS(v_hash::INTEGER);
END;
$$;

COMMENT ON FUNCTION calcular_quincena_hash IS 'Hash simple de fecha ETA para rotar paletas frontend (mod 4 → celeste/naranja/violeta/verde).';

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 4: Trigger para auto-poblar label_corto y hash al INSERT/UPDATE
-- ══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION trg_eta_catalogo_before_insert_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.label_corto := generar_eta_label_corto(NEW.fecha_arribo);
  NEW.quincena_hash := calcular_quincena_hash(NEW.fecha_arribo);
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_eta_catalogo_auto_labels
BEFORE INSERT OR UPDATE ON eta_catalogo
FOR EACH ROW
EXECUTE FUNCTION trg_eta_catalogo_before_insert_update();

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 5: Poblar catálogo con ETAs existentes en pedido_proveedor
-- ══════════════════════════════════════════════════════════════════════════════

INSERT INTO eta_catalogo (fecha_arribo, descripcion)
SELECT DISTINCT
  pp.fecha_arribo_estimada,
  'Arribo ' || TO_CHAR(pp.fecha_arribo_estimada, 'Month YYYY')
FROM pedido_proveedor pp
WHERE pp.fecha_arribo_estimada IS NOT NULL
  AND pp.fecha_arribo_estimada >= '2020-01-01'
ON CONFLICT (fecha_arribo) DO NOTHING;

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 6: Verificación
-- ══════════════════════════════════════════════════════════════════════════════

DO $$
DECLARE
  v_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO v_count FROM eta_catalogo WHERE activo = true;
  RAISE NOTICE '[057] ✓ eta_catalogo creado con % fechas ETA activas', v_count;
END;
$$;
