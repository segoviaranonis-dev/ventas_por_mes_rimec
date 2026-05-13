-- OT-2026-049 (rev 2): Poblar linea.genero_id según MARCA en v_stock_web
-- Fecha: 2026-05-08 (actualizado con 018: ya no se usa columna texto linea.genero)
-- Requiere filas en maestro public.genero con codigo coherente (p. ej. DAMAS, NIÑAS, NIÑOS, CABALLEROS).

-- DAMAS (marcas femeninas)
UPDATE linea SET genero_id = (SELECT id FROM genero WHERE codigo = 'DAMAS' AND COALESCE(activo, true) LIMIT 1)
WHERE codigo_proveedor::text IN (
  SELECT DISTINCT trim(both from v.linea_codigo::text)
  FROM v_stock_web v
  WHERE v.marca IN ('VIZZANO', 'BEIRA RIO', 'MODARE', 'MOLECA', 'ACTVITTA')
);

-- NIÑAS (MOLEKINHA)
UPDATE linea SET genero_id = (SELECT id FROM genero WHERE codigo = 'NIÑAS' AND COALESCE(activo, true) LIMIT 1)
WHERE codigo_proveedor::text IN (
  SELECT DISTINCT trim(both from v.linea_codigo::text)
  FROM v_stock_web v
  WHERE v.marca = 'MOLEKINHA'
);

-- NIÑOS (MOLEKINHO)
UPDATE linea SET genero_id = (SELECT id FROM genero WHERE codigo = 'NIÑOS' AND COALESCE(activo, true) LIMIT 1)
WHERE codigo_proveedor::text IN (
  SELECT DISTINCT trim(both from v.linea_codigo::text)
  FROM v_stock_web v
  WHERE v.marca = 'MOLEKINHO'
);

-- CABALLEROS (BR SPORT)
UPDATE linea SET genero_id = (SELECT id FROM genero WHERE codigo = 'CABALLEROS' AND COALESCE(activo, true) LIMIT 1)
WHERE codigo_proveedor::text IN (
  SELECT DISTINCT trim(both from v.linea_codigo::text)
  FROM v_stock_web v
  WHERE v.marca = 'BR SPORT'
);
