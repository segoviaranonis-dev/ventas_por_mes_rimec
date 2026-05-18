-- =============================================================================
-- 034 · Vaciado operativo de staging retail (multi-tienda / importadora)
-- ADVERTENCIA: al aplicar esta migración se borran TODAS las filas de staging.
-- Si preferís no vaciar al correr migraciones, mové solo el TRUNCATE a un script
-- manual y dejá este archivo como comentario / doc.
-- Propósito: dejar la tabla lista para reimportar con la ley de pilares
--            (alta automática de línea+referencia+linea_referencia por rango).
-- No elimina: marca/genero/material/color «Otros» de 033, ni filas de linea
--              / referencia / linea_referencia del catálogo global.
-- =============================================================================

TRUNCATE public.retail_multitienda_staging RESTART IDENTITY;

COMMENT ON TABLE public.retail_multitienda_staging IS
  'Staging Excel multi-tienda. Tras 034 vaciado para reimport; FK L+R se crean en pilares si faltan (rango mil líneas, ver fk_resolve).';
