-- OT-2026-049: Poblar linea.genero_id (clasificación por proveedor / combinación)
-- Fecha: 2026-05-08 (rev 2: columna texto linea.genero eliminada en migración 018)
-- Requiere maestro genero con codigo DAMAS, NIÑAS, NIÑOS, CABALLEROS según corresponda.

-- DAMAS (marcas femeninas vía proveedor)
UPDATE linea SET genero_id = (SELECT id FROM genero WHERE codigo = 'DAMAS' AND COALESCE(activo, true) LIMIT 1)
WHERE id IN (
  SELECT DISTINCT l.id FROM linea l
  JOIN combinacion c ON c.linea_id = l.id
  JOIN referencia r ON r.id = c.referencia_id
  WHERE l.proveedor_id IN (
    SELECT id FROM proveedor_importacion WHERE nombre ILIKE ANY(
      ARRAY['%VIZZANO%','%BEIRA RIO%','%MODARE%','%MOLECA%','%ACTVITTA%']
    )
  )
);

-- NIÑAS (MOLEKINHA)
UPDATE linea SET genero_id = (SELECT id FROM genero WHERE codigo = 'NIÑAS' AND COALESCE(activo, true) LIMIT 1)
WHERE id IN (
  SELECT DISTINCT l.id FROM linea l
  WHERE l.proveedor_id IN (
    SELECT id FROM proveedor_importacion WHERE nombre ILIKE '%MOLEKINHA%'
  )
);

-- NIÑOS (MOLEKINHO)
UPDATE linea SET genero_id = (SELECT id FROM genero WHERE codigo = 'NIÑOS' AND COALESCE(activo, true) LIMIT 1)
WHERE id IN (
  SELECT DISTINCT l.id FROM linea l
  WHERE l.proveedor_id IN (
    SELECT id FROM proveedor_importacion WHERE nombre ILIKE '%MOLEKINHO%'
  )
);

-- CABALLEROS (BR SPORT + marcas masculinas)
UPDATE linea SET genero_id = (SELECT id FROM genero WHERE codigo = 'CABALLEROS' AND COALESCE(activo, true) LIMIT 1)
WHERE id IN (
  SELECT DISTINCT l.id FROM linea l
  WHERE l.proveedor_id IN (
    SELECT id FROM proveedor_importacion WHERE nombre ILIKE '%BR SPORT%'
  )
);
