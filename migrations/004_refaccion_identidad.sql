-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRACIÓN 004: Refacción de Identidad + Quinto Pilar + Trazabilidad
-- Ejecutada: 2026-04-21 ✅
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

-- ── Drop vistas que dependen de columnas a renombrar ─────────────────────
DROP VIEW IF EXISTS v_stock_web;
DROP VIEW IF EXISTS v_catalogo_web;

-- ═══════════════════════════════════════════════════════════════════════════
-- PASO 1 — MIGRACIÓN DE DATOS HISTÓRICOS
-- ═══════════════════════════════════════════════════════════════════════════

-- 1a. precio_evento: proveedor_id nullable → poblar → NOT NULL
ALTER TABLE precio_evento
    ADD COLUMN IF NOT EXISTS proveedor_id BIGINT
    REFERENCES proveedor_importacion(id);

UPDATE precio_evento SET proveedor_id = 654 WHERE proveedor_id IS NULL;

ALTER TABLE precio_evento ALTER COLUMN proveedor_id SET NOT NULL;

-- 1b. precio_lista: trazabilidad (nullable → poblar → NOT NULL en críticos)
ALTER TABLE precio_lista
    ADD COLUMN IF NOT EXISTS dolar_aplicado       NUMERIC,
    ADD COLUMN IF NOT EXISTS factor_aplicado      NUMERIC,
    ADD COLUMN IF NOT EXISTS indice_aplicado      NUMERIC,
    ADD COLUMN IF NOT EXISTS descuento_1_aplicado NUMERIC,
    ADD COLUMN IF NOT EXISTS descuento_2_aplicado NUMERIC,
    ADD COLUMN IF NOT EXISTS descuento_3_aplicado NUMERIC,
    ADD COLUMN IF NOT EXISTS descuento_4_aplicado NUMERIC,
    ADD COLUMN IF NOT EXISTS nombre_caso_aplicado TEXT;

UPDATE precio_lista SET
    dolar_aplicado       = 0,
    factor_aplicado      = 0,
    indice_aplicado      = 0,
    nombre_caso_aplicado = 'MIGRADO'
WHERE nombre_caso_aplicado IS NULL;

ALTER TABLE precio_lista
    ALTER COLUMN dolar_aplicado       SET NOT NULL,
    ALTER COLUMN factor_aplicado      SET NOT NULL,
    ALTER COLUMN indice_aplicado      SET NOT NULL,
    ALTER COLUMN nombre_caso_aplicado SET NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════
-- PASO 2 — REFACCIÓN DE LOS 5 PILARES
-- ═══════════════════════════════════════════════════════════════════════════

-- ── linea ──────────────────────────────────────────────────────────────────
ALTER TABLE linea RENAME COLUMN codigo TO codigo_proveedor;
ALTER TABLE linea ALTER COLUMN codigo_proveedor TYPE BIGINT
    USING codigo_proveedor::BIGINT;
ALTER TABLE linea ADD CONSTRAINT uq_linea_proveedor_codigo
    UNIQUE(proveedor_id, codigo_proveedor);

-- ── referencia ─────────────────────────────────────────────────────────────
ALTER TABLE referencia RENAME COLUMN codigo TO codigo_proveedor;
ALTER TABLE referencia ALTER COLUMN codigo_proveedor TYPE BIGINT
    USING codigo_proveedor::BIGINT;
ALTER TABLE referencia
    ADD COLUMN IF NOT EXISTS proveedor_id BIGINT REFERENCES proveedor_importacion(id);
UPDATE referencia r
    SET proveedor_id = (SELECT proveedor_id FROM linea WHERE id = r.linea_id)
    WHERE r.proveedor_id IS NULL;
ALTER TABLE referencia ALTER COLUMN proveedor_id SET NOT NULL;
ALTER TABLE referencia ADD CONSTRAINT uq_referencia_proveedor_linea_codigo
    UNIQUE(proveedor_id, linea_id, codigo_proveedor);

CREATE OR REPLACE FUNCTION fn_validar_proveedor_referencia()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.proveedor_id != (SELECT proveedor_id FROM linea WHERE id = NEW.linea_id) THEN
        RAISE EXCEPTION
            'proveedor_id de referencia (%) no coincide con proveedor_id de su linea padre (%)',
            NEW.proveedor_id,
            (SELECT proveedor_id FROM linea WHERE id = NEW.linea_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_proveedor_referencia
BEFORE INSERT OR UPDATE ON referencia
FOR EACH ROW EXECUTE FUNCTION fn_validar_proveedor_referencia();

-- ── material ───────────────────────────────────────────────────────────────
ALTER TABLE material RENAME COLUMN codigo TO codigo_proveedor;
ALTER TABLE material ALTER COLUMN codigo_proveedor TYPE BIGINT
    USING codigo_proveedor::BIGINT;
ALTER TABLE material ADD CONSTRAINT uq_material_proveedor_codigo
    UNIQUE(proveedor_id, codigo_proveedor);

-- ── color (proveedor_id ya existe desde migración 003) ────────────────────
ALTER TABLE color RENAME COLUMN codigo TO codigo_proveedor;
ALTER TABLE color ALTER COLUMN codigo_proveedor TYPE BIGINT
    USING codigo_proveedor::BIGINT;
ALTER TABLE color ADD CONSTRAINT uq_color_proveedor_codigo
    UNIQUE(proveedor_id, codigo_proveedor);

-- ── talla — refacción de tabla existente ───────────────────────────────────
-- Estructura anterior: id, codigo(text), tipo(text), orden_visual, activo, created_at
-- codigo → talla_etiqueta (display: "37", "38", "37/38", "P", "M")
-- tipo   → sistema        ("NUMERICO", "BR", "EU", etc.)
ALTER TABLE talla RENAME COLUMN codigo TO talla_etiqueta;
ALTER TABLE talla RENAME COLUMN tipo   TO sistema;

ALTER TABLE talla
    ADD COLUMN IF NOT EXISTS proveedor_id     BIGINT REFERENCES proveedor_importacion(id),
    ADD COLUMN IF NOT EXISTS codigo_proveedor BIGINT,
    ADD COLUMN IF NOT EXISTS talla_valor      NUMERIC;

-- talla_valor desde etiqueta para registros numéricos simples
UPDATE talla SET talla_valor = talla_etiqueta::NUMERIC
WHERE talla_etiqueta ~ '^\d+(\.\d+)?$';

-- UNIQUE: solo aplica cuando proveedor_id + codigo_proveedor estén poblados (re-importación)
ALTER TABLE talla ADD CONSTRAINT uq_talla_proveedor_codigo
    UNIQUE(proveedor_id, codigo_proveedor);

-- ═══════════════════════════════════════════════════════════════════════════
-- PASO 3 — NUEVA TABLA pedido_grada
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE pedido_grada (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pedido_id      BIGINT NOT NULL,
    proveedor_id   BIGINT NOT NULL REFERENCES proveedor_importacion(id),
    talla_id       BIGINT NOT NULL REFERENCES talla(id),
    talla_etiqueta TEXT NOT NULL,
    talla_valor    NUMERIC NOT NULL,
    cantidad       INTEGER NOT NULL,
    posicion       INTEGER NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_pedido_grada UNIQUE(pedido_id, talla_id)
);

ALTER TABLE pedido_grada ADD CONSTRAINT fk_pedido_grada_pedido
    FOREIGN KEY (pedido_id) REFERENCES pedido_proveedor(id);

-- ═══════════════════════════════════════════════════════════════════════════
-- PASO 4 — RECREAR VISTAS CON NUEVOS NOMBRES DE COLUMNAS
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_catalogo_web AS
SELECT
    c.id                          AS combinacion_id,
    pw.id                         AS proveedor_id,
    pw.nombre                     AS proveedor_nombre,
    pw.imagen_bucket,
    pw.imagen_formula,
    l.codigo_proveedor            AS linea_codigo,
    l.descripcion                 AS linea_descripcion,
    ref.codigo_proveedor          AS referencia_codigo,
    ref.descripcion               AS referencia_descripcion,
    mat.codigo_proveedor          AS material_codigo,
    mat.descripcion               AS material_descripcion,
    col.codigo_proveedor          AS color_codigo,
    col.nombre                    AS color_nombre,
    col.hex_web,
    ta.talla_etiqueta             AS talla_codigo,
    ta.sistema                    AS talla_tipo,
    ta.orden_visual               AS talla_orden,
    p.valor                       AS precio_web,
    p.lista_id,
    COALESCE(sa.stock, 0::bigint) AS stock_web
FROM combinacion c
JOIN proveedor_web pw  ON pw.id  = c.proveedor_id
JOIN linea l           ON l.id   = c.linea_id
JOIN referencia ref    ON ref.id = c.referencia_id
JOIN material mat      ON mat.id = c.material_id
JOIN color col         ON col.id = c.color_id
JOIN talla ta          ON ta.id  = c.talla_id
LEFT JOIN precio p     ON p.combinacion_id = c.id
    AND p.fecha_hasta IS NULL
    AND EXISTS (
        SELECT 1 FROM lista_precio lp
        WHERE lp.id = p.lista_id AND lp.tipo = 'WEB' AND lp.activa = true
    )
LEFT JOIN v_stock_actual sa ON sa.combinacion_id = c.id
    AND EXISTS (
        SELECT 1 FROM almacen al
        WHERE al.id = sa.almacen_id AND al.nombre = 'ALM_WEB_01'
    )
WHERE c.activo_web = true AND pw.activo = true;

CREATE OR REPLACE VIEW v_stock_web AS
WITH mov_agg AS (
    SELECT
        md.combinacion_id,
        sum(
            CASE
                WHEN m.tipo = 'INGRESO_COMPRA' AND m.almacen_destino_id = 1 THEN md.cantidad * md.signo
                WHEN m.tipo = 'VENTA_WEB'      AND m.almacen_origen_id  = 1 THEN -md.cantidad
                ELSE 0
            END
        ) AS stock_web,
        max(
            CASE
                WHEN m.tipo = 'INGRESO_COMPRA' THEN (tr.snapshot_json->>'id_marca')::integer
                ELSE NULL::integer
            END
        ) AS id_marca_ref
    FROM movimiento_detalle md
    JOIN movimiento m ON m.id = md.movimiento_id
    LEFT JOIN traspaso tr ON tr.numero_registro = m.documento_ref
    WHERE m.estado = 'CONFIRMADO'
      AND (
          (m.tipo = 'INGRESO_COMPRA' AND m.almacen_destino_id = 1)
          OR (m.tipo = 'VENTA_WEB'   AND m.almacen_origen_id  = 1)
      )
    GROUP BY md.combinacion_id
    HAVING sum(
        CASE
            WHEN m.tipo = 'INGRESO_COMPRA' AND m.almacen_destino_id = 1 THEN md.cantidad * md.signo
            WHEN m.tipo = 'VENTA_WEB'      AND m.almacen_origen_id  = 1 THEN -md.cantidad
            ELSE 0
        END
    ) > 0
)
SELECT
    c.id                                        AS combinacion_id,
    COALESCE(mv.descp_marca, '—')               AS marca,
    l.codigo_proveedor                          AS linea_codigo,
    l.descripcion                               AS linea_descripcion,
    r.codigo_proveedor                          AS referencia_codigo,
    r.descripcion                               AS referencia_descripcion,
    c.material_id,
    mat.descripcion                             AS material_descripcion,
    c.color_id,
    col.nombre                                  AS color_nombre,
    col.hex_web,
    (
        SELECT ppd.id_material FROM pedido_proveedor_detalle ppd
        WHERE ppd.linea      = l.codigo_proveedor::text
          AND ppd.referencia = r.codigo_proveedor::text
          AND ppd.descp_material = mat.descripcion
          AND ppd.id_material IS NOT NULL
        LIMIT 1
    )                                           AS id_material_f9,
    (
        SELECT ppd.id_color FROM pedido_proveedor_detalle ppd
        WHERE ppd.linea      = l.codigo_proveedor::text
          AND ppd.referencia = r.codigo_proveedor::text
          AND ppd.descp_color = col.nombre
          AND ppd.id_color IS NOT NULL
        LIMIT 1
    )                                           AS id_color_f9,
    tl.talla_etiqueta                           AS talla_codigo,
    tl.orden_visual                             AS talla_orden,
    agg.stock_web,
    NULL::numeric                               AS precio_web,
    COALESCE(ge.descp_grupo_estilo, '')         AS estilo,
    ge.id_grupo_estilo                          AS estilo_id
FROM mov_agg agg
JOIN combinacion c     ON c.id   = agg.combinacion_id
JOIN linea l           ON l.id   = c.linea_id
LEFT JOIN grupo_estilo_v2 ge ON ge.id_grupo_estilo = l.grupo_estilo_id
JOIN referencia r      ON r.id   = c.referencia_id
LEFT JOIN material mat ON mat.id = c.material_id
LEFT JOIN color col    ON col.id = c.color_id
JOIN talla tl          ON tl.id  = c.talla_id
LEFT JOIN marca_v2 mv  ON mv.id_marca = agg.id_marca_ref;

COMMIT;
