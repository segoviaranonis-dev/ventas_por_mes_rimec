-- OT-2026-047: Tabla de trazabilidad de costos al confirmar proforma
-- Fecha: 2026-05-07
-- Propósito: Registrar snapshot de costos (dólar, factor, índice, FOB, listas) al confirmar cada PP

CREATE TABLE IF NOT EXISTS snapshot_costos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pp_id BIGINT NOT NULL REFERENCES pedido_proveedor(id) ON DELETE CASCADE,
    evento_id BIGINT,

    -- Parámetros de costo al momento de confirmación
    dolar_politica NUMERIC(12,4),
    factor NUMERIC(12,6),
    indice NUMERIC(12,6),
    fob_usd NUMERIC(12,4),

    -- Listas de precio calculadas
    lpn NUMERIC(12,2),
    lpc03 NUMERIC(12,2),
    lpc04 NUMERIC(12,2),

    created_at TIMESTAMPTZ DEFAULT now()
);

-- Índice para búsquedas por PP
CREATE INDEX IF NOT EXISTS idx_snapshot_costos_pp_id ON snapshot_costos(pp_id);

-- Índice para búsquedas por fecha
CREATE INDEX IF NOT EXISTS idx_snapshot_costos_created_at ON snapshot_costos(created_at);

-- Comentarios
COMMENT ON TABLE snapshot_costos IS 'Trazabilidad de costos al confirmar proforma - OT-2026-047';
COMMENT ON COLUMN snapshot_costos.pp_id IS 'FK a pedido_proveedor - cada confirmación genera un snapshot';
COMMENT ON COLUMN snapshot_costos.evento_id IS 'ID del evento de confirmación (opcional)';
COMMENT ON COLUMN snapshot_costos.dolar_politica IS 'Dólar política usado en el cálculo';
COMMENT ON COLUMN snapshot_costos.factor IS 'Factor de costo aplicado';
COMMENT ON COLUMN snapshot_costos.indice IS 'Índice de ajuste aplicado';
COMMENT ON COLUMN snapshot_costos.fob_usd IS 'FOB en USD del producto';
COMMENT ON COLUMN snapshot_costos.lpn IS 'Lista Precio Normal calculada';
COMMENT ON COLUMN snapshot_costos.lpc03 IS 'Lista Precio C03 calculada';
COMMENT ON COLUMN snapshot_costos.lpc04 IS 'Lista Precio C04 calculada';
