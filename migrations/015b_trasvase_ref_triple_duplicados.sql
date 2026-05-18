-- ═══════════════════════════════════════════════════════════════════════════
-- 015b — Trasvase seguro: solo duplicados (proveedor_id, linea_id, codigo_proveedor)
--
-- Alineado a lógica de negocio (Héctor):
--   · Referencia sola no significa nada → siempre anclada a línea.
--   · Línea + Referencia = estilo (linea_referencia).
--   · Línea + Referencia + Material = precio (precio_lista / evento).
-- NO se fusionan filas con el mismo código en distintas líneas: son identidades distintas.
--
-- Antes: ejecutar `python scripts/diag_referencia_duplicados.py` y revisar
-- `_diag_referencia_salida.txt`. Si hay grupos REVISAR_lineas_distintas, NO ejecutar
-- este script para fusionar por código solo; el mapa aquí usa solo el triple.
--
-- Incluye combinacion: obligatorio si se borran filas en referencia (integridad FK).
-- ═══════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TEMP TABLE _ref_id_map (id_old BIGINT PRIMARY KEY, id_new BIGINT NOT NULL);

INSERT INTO _ref_id_map (id_old, id_new)
SELECT r.id, g.id_keep
FROM referencia r
INNER JOIN (
    SELECT proveedor_id, linea_id, codigo_proveedor, MAX(id) AS id_keep
    FROM referencia
    GROUP BY proveedor_id, linea_id, codigo_proveedor
    HAVING COUNT(*) > 1
) g
  ON r.proveedor_id = g.proveedor_id
 AND r.linea_id = g.linea_id
 AND r.codigo_proveedor = g.codigo_proveedor
WHERE r.id <> g.id_keep;

-- Si no hay mapa, el resto es no-op (0 filas afectadas).
SELECT COUNT(*) AS filas_mapa_ref FROM _ref_id_map;

-- precio_lista
UPDATE precio_lista pl
SET referencia_id = m.id_new
FROM _ref_id_map m
WHERE pl.referencia_id = m.id_old;

-- linea_referencia: quitar filas duplicadas del par (linea_id, id_new) cuando ya existe keeper
DELETE FROM linea_referencia lr
USING _ref_id_map m
WHERE lr.referencia_id = m.id_old
  AND EXISTS (
    SELECT 1
    FROM linea_referencia k
    WHERE k.linea_id = lr.linea_id
      AND k.referencia_id = m.id_new
  );

UPDATE linea_referencia lr
SET referencia_id = m.id_new
FROM _ref_id_map m
WHERE lr.referencia_id = m.id_old;

-- combinacion (necesario antes de borrar referencia)
UPDATE combinacion c
SET referencia_id = m.id_new
FROM _ref_id_map m
WHERE c.referencia_id = m.id_old
  AND NOT EXISTS (
    SELECT 1
    FROM combinacion c2
    WHERE c2.linea_id = c.linea_id
      AND c2.referencia_id = m.id_new
      AND c2.material_id = c.material_id
      AND c2.color_id = c.color_id
      AND c2.talla_id = c.talla_id
      AND c2.id <> c.id
  );

-- Si quedan combinacion apuntando a id_old por colisión del quinto pilar, el DELETE fallará por FK.
DELETE FROM referencia r
USING _ref_id_map m
WHERE r.id = m.id_old;

COMMIT;
