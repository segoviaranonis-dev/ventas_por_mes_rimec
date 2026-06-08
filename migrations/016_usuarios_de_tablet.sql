-- ============================================================
-- Migración 016: Tabla usuarios_de_tablet
-- Herramienta tablet para ventas en tienda física
-- ============================================================

CREATE TABLE IF NOT EXISTS usuarios_de_tablet (
  id BIGSERIAL PRIMARY KEY,

  -- Datos personales
  cedula VARCHAR(20) NOT NULL UNIQUE,
  nombres VARCHAR(100) NOT NULL,
  apellidos VARCHAR(100) NOT NULL,
  telefono VARCHAR(20),

  -- Código de vendedor (número corto)
  codigo_vendedor INTEGER NOT NULL UNIQUE,

  -- Estado
  activo BOOLEAN DEFAULT TRUE,

  -- Auditoría
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Constraints
  CONSTRAINT chk_codigo_vendedor_positivo CHECK (codigo_vendedor > 0),
  CONSTRAINT chk_cedula_no_vacia CHECK (LENGTH(TRIM(cedula)) > 0)
);

-- Índices para búsqueda rápida
CREATE INDEX IF NOT EXISTS idx_usuarios_tablet_codigo ON usuarios_de_tablet(codigo_vendedor);
CREATE INDEX IF NOT EXISTS idx_usuarios_tablet_cedula ON usuarios_de_tablet(cedula);
CREATE INDEX IF NOT EXISTS idx_usuarios_tablet_activo ON usuarios_de_tablet(activo) WHERE activo = TRUE;

-- Comentarios
COMMENT ON TABLE usuarios_de_tablet IS 'Vendedores de tienda física para herramienta tablet';
COMMENT ON COLUMN usuarios_de_tablet.cedula IS 'Cédula de identidad (único)';
COMMENT ON COLUMN usuarios_de_tablet.codigo_vendedor IS 'Código numérico corto para login rápido (ej: 22)';
COMMENT ON COLUMN usuarios_de_tablet.activo IS 'FALSE = desactivado sin eliminar del sistema';
