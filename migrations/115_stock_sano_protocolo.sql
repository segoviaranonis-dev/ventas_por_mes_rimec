-- 115 — Protocolo Stock Sano: precio vigente por depósito + historial de ingresos
-- Primer depósito: ALM_WEB_01 (id=1). Motor de precio = aduanero en compra→depósito.

-- Tabla canon: precio de venta vigente por almacén + triplete L+R+Material
CREATE TABLE IF NOT EXISTS stock_sano_deposito (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  almacen_id        BIGINT NOT NULL REFERENCES almacen(id),
  linea_id          BIGINT NOT NULL REFERENCES linea(id),
  referencia_id     BIGINT NOT NULL REFERENCES referencia(id),
  material_id       BIGINT REFERENCES material(id),
  material_id_key   BIGINT GENERATED ALWAYS AS (COALESCE(material_id, 0)) STORED,
  precio_venta      NUMERIC NOT NULL CHECK (precio_venta > 0),
  lpn               NUMERIC,
  caso_codigo       TEXT,
  markup_pct        NUMERIC(5,2),
  protocolo_version TEXT NOT NULL DEFAULT 'STOCK_SANO_v1',
  vigente_desde     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_stock_sano_triplete UNIQUE (almacen_id, linea_id, referencia_id, material_id_key)
);

COMMENT ON TABLE stock_sano_deposito IS
  'Protocolo Stock Sano: precio de venta canonico por depósito y triplete L+R+Material.';

-- Depósitos con protocolo activo
CREATE TABLE IF NOT EXISTS stock_sano_almacen (
  almacen_id        BIGINT PRIMARY KEY REFERENCES almacen(id),
  lista_precio_id   BIGINT REFERENCES lista_precio(id),
  protocolo_activo  BOOLEAN NOT NULL DEFAULT true,
  activado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE stock_sano_almacen IS
  'Registro de depósitos bajo protocolo Stock Sano y su lista_precio WEB asociada.';

-- Historial / auditoría (ingresos, conflictos, decisiones)
CREATE TABLE IF NOT EXISTS stock_sano_historial (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  stock_sano_deposito_id  BIGINT REFERENCES stock_sano_deposito(id),
  almacen_id              BIGINT NOT NULL REFERENCES almacen(id),
  linea_id                BIGINT NOT NULL REFERENCES linea(id),
  referencia_id           BIGINT NOT NULL REFERENCES referencia(id),
  material_id             BIGINT REFERENCES material(id),
  traspaso_id             BIGINT REFERENCES traspaso(id),
  movimiento_id           BIGINT REFERENCES movimiento(id),
  evento                  TEXT NOT NULL CHECK (evento IN (
    'ALTA_INICIAL', 'INGRESO_SANO', 'CONFLICTO', 'DECISION_NUEVO', 'DECISION_MANTENER'
  )),
  precio_anterior         NUMERIC,
  precio_propuesto        NUMERIC,
  precio_aplicado         NUMERIC NOT NULL,
  lpn_entrante            NUMERIC,
  caso_entrante           TEXT,
  decision                TEXT CHECK (decision IN ('AUTO_SANO', 'ACEPTAR_NUEVO', 'MANTENER_VIEJO')),
  usuario_id              BIGINT REFERENCES usuario_v2(id_usuario),
  notas                   TEXT,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stock_sano_hist_almacen ON stock_sano_historial(almacen_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stock_sano_hist_traspaso ON stock_sano_historial(traspaso_id);

COMMENT ON TABLE stock_sano_historial IS
  'Trazabilidad Stock Sano: cada ingreso, conflicto de precio y decision del Director.';

-- Vista operativa: stock en depósito + precio canon + estado sano
CREATE OR REPLACE VIEW v_stock_sano_deposito AS
WITH det AS (
  SELECT
    md.combinacion_id,
    c.linea_id,
    c.referencia_id,
    c.material_id,
    COALESCE(c.material_id, 0) AS material_id_key,
    l.codigo_proveedor::text AS linea,
    r.codigo_proveedor::text AS referencia,
    COALESCE(mat.descripcion, '—') AS material,
    COALESCE(col.nombre, '—') AS color,
    tl.talla_etiqueta AS talla,
    SUM(md.cantidad * md.signo)::int AS stock_pares,
    m.almacen_destino_id AS almacen_id
  FROM movimiento_detalle md
  JOIN movimiento m ON m.id = md.movimiento_id
  JOIN combinacion c ON c.id = md.combinacion_id
  JOIN linea l ON l.id = c.linea_id
  JOIN referencia r ON r.id = c.referencia_id
  LEFT JOIN material mat ON mat.id = c.material_id
  LEFT JOIN color col ON col.id = c.color_id
  JOIN talla tl ON tl.id = c.talla_id
  WHERE m.estado = 'CONFIRMADO'
    AND m.tipo = 'INGRESO_COMPRA'
  GROUP BY md.combinacion_id, c.linea_id, c.referencia_id, c.material_id,
           l.codigo_proveedor, r.codigo_proveedor, mat.descripcion, col.nombre,
           tl.talla_etiqueta, m.almacen_destino_id
  HAVING SUM(md.cantidad * md.signo) > 0
)
SELECT
  d.almacen_id,
  a.nombre AS almacen_nombre,
  d.combinacion_id,
  d.linea,
  d.referencia,
  d.material,
  d.color,
  d.talla,
  d.stock_pares,
  ssd.id AS stock_sano_id,
  ssd.precio_venta,
  ssd.lpn,
  ssd.caso_codigo,
  ssd.markup_pct,
  CASE
    WHEN ssd.id IS NULL THEN 'SIN_PROTOCOLO'
    WHEN ssd.precio_venta IS NULL THEN 'SIN_PRECIO'
    ELSE 'SANO'
  END AS estado_stock_sano,
  sa.protocolo_activo
FROM det d
JOIN almacen a ON a.id = d.almacen_id
LEFT JOIN stock_sano_almacen sa ON sa.almacen_id = d.almacen_id AND sa.protocolo_activo = true
LEFT JOIN stock_sano_deposito ssd ON ssd.almacen_id = d.almacen_id
  AND ssd.linea_id = d.linea_id
  AND ssd.referencia_id = d.referencia_id
  AND ssd.material_id_key = d.material_id_key;

COMMENT ON VIEW v_stock_sano_deposito IS
  'Stock por combinación en depósitos con precio canon Stock Sano y estado SANO/SIN_*';
