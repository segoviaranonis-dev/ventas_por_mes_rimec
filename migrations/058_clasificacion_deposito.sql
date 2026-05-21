-- Migración 058: Tablas clasificacion_stock y deposito (stock local futuro)
-- OT: OT-RIMEC-WEB-TARJETAS-MULTI-ORIGEN-001
-- Autor: Claude Code
-- Fecha: 2026-05-19
--
-- Objetivo: Preparar infraestructura para tarjetas PRONTA ENTREGA (stock local).
-- Cuando stock físico exista: tarjeta = DEPOSITO + CLASIFICACIÓN (Normal/Oferta/Liquidación).

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 1: Tabla clasificacion_stock (Normal / Oferta / Liquidación)
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS clasificacion_stock (
  id              BIGSERIAL PRIMARY KEY,
  codigo          TEXT NOT NULL UNIQUE,
  descripcion     TEXT NOT NULL,
  orden_ui        INTEGER DEFAULT 0,         -- Orden en dropdown/filtros web
  color_badge     TEXT,                      -- Hex color para badge frontend (#059669, #F97316, etc.)
  activo          BOOLEAN DEFAULT true,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),

  CONSTRAINT clasificacion_stock_codigo_mayuscula CHECK (codigo = UPPER(codigo)),
  CONSTRAINT clasificacion_stock_descripcion_no_vacia CHECK (LENGTH(TRIM(descripcion)) > 0)
);

CREATE INDEX idx_clasificacion_stock_codigo ON clasificacion_stock(codigo) WHERE activo = true;
CREATE INDEX idx_clasificacion_stock_orden ON clasificacion_stock(orden_ui, activo);

COMMENT ON TABLE clasificacion_stock IS 'Clasificación de stock local para tarjetas PRONTA ENTREGA: Normal, Oferta, Liquidación.';
COMMENT ON COLUMN clasificacion_stock.codigo IS 'Código único mayúscula (ej. NORMAL, OFERTA, LIQUIDACION).';
COMMENT ON COLUMN clasificacion_stock.orden_ui IS 'Orden de presentación en UI web (menor = primero).';
COMMENT ON COLUMN clasificacion_stock.color_badge IS 'Color hex para badge frontend. Verde=Normal, Naranja=Oferta, Rojo=Liquidación.';

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 2: Poblar clasificaciones P0
-- ══════════════════════════════════════════════════════════════════════════════

INSERT INTO clasificacion_stock (codigo, descripcion, orden_ui, color_badge) VALUES
  ('NORMAL',      'Normal',      1, '#059669'),  -- Verde (stock regular)
  ('OFERTA',      'Oferta',      2, '#F97316'),  -- Naranja (promoción)
  ('LIQUIDACION', 'Liquidación', 3, '#DC2626')   -- Rojo (clearance)
ON CONFLICT (codigo) DO UPDATE SET
  descripcion = EXCLUDED.descripcion,
  orden_ui = EXCLUDED.orden_ui,
  color_badge = EXCLUDED.color_badge,
  updated_at = NOW();

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 3: Tabla deposito (almacenes físicos)
-- ══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS deposito (
  id              BIGSERIAL PRIMARY KEY,
  codigo          TEXT NOT NULL UNIQUE,
  nombre          TEXT NOT NULL,
  direccion       TEXT,
  ciudad          TEXT,
  pais            TEXT DEFAULT 'PY',
  activo          BOOLEAN DEFAULT true,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),

  CONSTRAINT deposito_codigo_mayuscula CHECK (codigo = UPPER(codigo)),
  CONSTRAINT deposito_nombre_no_vacio CHECK (LENGTH(TRIM(nombre)) > 0)
);

CREATE INDEX idx_deposito_codigo ON deposito(codigo) WHERE activo = true;
CREATE INDEX idx_deposito_pais ON deposito(pais, activo);

COMMENT ON TABLE deposito IS 'Depósitos físicos RIMEC para stock local (PRONTA ENTREGA).';
COMMENT ON COLUMN deposito.codigo IS 'Código único depósito (ej. RIMEC_PY, RIMEC_AR, DEP_ZONA_ESTE).';
COMMENT ON COLUMN deposito.nombre IS 'Nombre completo del depósito para display UI.';

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 4: Poblar depósitos P0 (Paraguay principal)
-- ══════════════════════════════════════════════════════════════════════════════

INSERT INTO deposito (codigo, nombre, ciudad, pais) VALUES
  ('RIMEC_PY', 'RIMEC Paraguay - Depósito Central', 'Asunción', 'PY'),
  ('RIMEC_AR', 'RIMEC Argentina', 'Buenos Aires', 'AR')
ON CONFLICT (codigo) DO UPDATE SET
  nombre = EXCLUDED.nombre,
  ciudad = EXCLUDED.ciudad,
  pais = EXCLUDED.pais,
  updated_at = NOW();

-- ══════════════════════════════════════════════════════════════════════════════
-- PASO 5: Verificación
-- ══════════════════════════════════════════════════════════════════════════════

DO $$
DECLARE
  v_clasificaciones INTEGER;
  v_depositos INTEGER;
BEGIN
  SELECT COUNT(*) INTO v_clasificaciones FROM clasificacion_stock WHERE activo = true;
  SELECT COUNT(*) INTO v_depositos FROM deposito WHERE activo = true;

  RAISE NOTICE '[058] ✓ clasificacion_stock creado con % registros', v_clasificaciones;
  RAISE NOTICE '[058] ✓ deposito creado con % almacenes', v_depositos;
END;
$$;
