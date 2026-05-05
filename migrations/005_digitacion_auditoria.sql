-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 005: Módulo Digitación + Auditoría Forense
-- Referencia: docs/ALBANIL_MODULO_DIGITACION.md
-- Ejecutar en Supabase SQL Editor
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ───────────────────────────────────────────────────────────────────────────
-- 1. flujo_auditoria — registro forense inmutable de transiciones de estado
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS flujo_auditoria (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entidad         TEXT        NOT NULL,
    entidad_id      BIGINT      NOT NULL,
    nro_registro    TEXT,
    accion          TEXT        NOT NULL,
    estado_antes    TEXT,
    estado_despues  TEXT,
    snap            JSONB,
    usuario_id      BIGINT      REFERENCES usuario_v2(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_flujo_entidad
    ON flujo_auditoria (entidad, entidad_id);

CREATE INDEX IF NOT EXISTS idx_flujo_nro_registro
    ON flujo_auditoria (nro_registro);

CREATE INDEX IF NOT EXISTS idx_flujo_accion
    ON flujo_auditoria (accion);

COMMENT ON TABLE flujo_auditoria IS
    'Registro forense inmutable. Cada fila es una transición de estado auditada.';

-- ───────────────────────────────────────────────────────────────────────────
-- 2. intencion_compra — columnas de trazabilidad digitación
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE intencion_compra
    ADD COLUMN IF NOT EXISTS precio_evento_id   BIGINT  REFERENCES precio_evento(id),
    ADD COLUMN IF NOT EXISTS motivo_devolucion  TEXT,
    ADD COLUMN IF NOT EXISTS devuelto_at        TIMESTAMPTZ;

-- ───────────────────────────────────────────────────────────────────────────
-- 3. pedido_proveedor — columnas de digitación
-- ───────────────────────────────────────────────────────────────────────────
ALTER TABLE pedido_proveedor
    ADD COLUMN IF NOT EXISTS nro_factura_importacion  TEXT,
    ADD COLUMN IF NOT EXISTS estado_digitacion        TEXT
        DEFAULT 'ABIERTO'
        CHECK (estado_digitacion IN ('ABIERTO', 'CERRADO')),
    ADD COLUMN IF NOT EXISTS pares_comprometidos      INTEGER DEFAULT 0;

-- ───────────────────────────────────────────────────────────────────────────
-- 4. intencion_compra_pedido — tabla puente (corazón del módulo)
-- ───────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS intencion_compra_pedido (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    intencion_compra_id     BIGINT  NOT NULL REFERENCES intencion_compra(id),
    pedido_proveedor_id     BIGINT  NOT NULL REFERENCES pedido_proveedor(id),
    nro_pedido_fabrica      TEXT    NOT NULL,
    precio_evento_id        BIGINT  REFERENCES precio_evento(id),
    asignado_por            BIGINT  REFERENCES usuario_v2(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (intencion_compra_id)
);

CREATE INDEX IF NOT EXISTS idx_icp_pp
    ON intencion_compra_pedido (pedido_proveedor_id);

COMMENT ON TABLE intencion_compra_pedido IS
    'Puente IC → PP. Una IC solo puede estar en un PP (UNIQUE ic_id). '
    'nro_pedido_fabrica es obligatorio (número Beira Rio).';

COMMIT;
